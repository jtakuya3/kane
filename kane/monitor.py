"""ライブ監視：kabuステーションのPUSH配信 → ルール判定 → Slack通知＋CSV保存。

    python -m kane.monitor            # 監視
    python -m kane.monitor --check    # 接続確認（トークン・登録・現在の回転率を表示して終了）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time as _time
from datetime import datetime, time, timedelta

import websockets

from .config import Config, SymbolInfo, load_config
from .engine import Engine
from .kabu import KabuClient, KabuError, parse_push
from .models import Snapshot
from .scanner import RankingScanner
from .sinks import Notifier, Recorder

log = logging.getLogger("kane")


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def setup_logging(cfg: Config):
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(cfg.data_dir / f"monitor_{datetime.now():%Y%m%d}.log", encoding="utf-8"),
        ],
    )


def check(cfg: Config):
    client = KabuClient(cfg.base_url, cfg.password_file)
    client.get_token()
    print("トークン取得 OK")
    codes = [s.code for s in cfg.symbols]
    print("PUSH登録:", client.register(codes))
    for s in cfg.symbols:
        try:
            b = client.board(s.code)
        except KabuError as e:
            print(f"{s.code}: 取得失敗 {e}")
            continue
        vol, px, vwap = b.get("TradingVolume") or 0, b.get("CurrentPrice"), b.get("VWAP")
        turn = f"{vol / s.float_shares:.1%}" if s.float_shares else "-"
        dev = f"{px / vwap - 1:+.2%}" if px and vwap else "-"
        print(f"{s.code} {b.get('SymbolName', s.name)}: 現在値{px} 出来高{vol:,.0f} 回転率{turn} VWAP乖離{dev}")
    try:
        top = client.ranking(1, "ALL")[:5]
        print("ランキング（値上がり率 上位5）:", ", ".join(f"{r.get('Symbol')} {r.get('ChangePercentage')}%" for r in top))
    except KabuError as e:
        print("ランキング取得失敗:", e)
    notifier = Notifier(cfg.slack_webhook_file, cfg.slack_enabled, cfg.beep)
    print("Slack:", "設定あり" if notifier.url else "未設定（画面表示のみ）")


class Monitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = KabuClient(cfg.base_url, cfg.password_file)
        self.notifier = Notifier(cfg.slack_webhook_file, cfg.slack_enabled, cfg.beep)
        self.recorder = Recorder(cfg.data_dir, cfg.record_snapshots)
        self.engine = Engine(cfg.symbols, cfg.rules, on_bar=self.recorder.bar)
        self.start, self.end = _hm(cfg.session_start), _hm(cfg.session_end)
        self.count = 0
        pinned = {x.code for x in cfg.symbols}
        if len(pinned) > cfg.scanner.max_push:
            raise SystemExit(f"symbols.csv の固定銘柄が{len(pinned)}件あり、PUSH上限{cfg.scanner.max_push}を超えています")
        self.scanner = RankingScanner(self.client, cfg.scanner, pinned) if cfg.scanner.enabled else None

    def push_codes(self) -> list[str]:
        return self.scanner.push_codes() if self.scanner else [x.code for x in self.cfg.symbols]

    def load_limits(self, codes):
        """値幅制限の上限を /symbol から取る（取れなければ前日終値から計算）。"""
        for c in codes:
            if c in self.engine.limits:
                continue
            try:
                info = self.client.symbol(c)
                if info.get("UpperLimit"):
                    self.engine.limits[c] = float(info["UpperLimit"])
            except KabuError as e:
                log.warning("値幅制限の取得失敗 %s: %s", c, e)
            _time.sleep(0.12)

    async def emit(self, alerts):
        for a in alerts:
            self.count += 1
            self.recorder.alert(a)
            pop = a.rule in self.cfg.popup_rules or f"{a.rule}:{a.level}" in self.cfg.popup_rules
            await asyncio.to_thread(self.notifier.send, a.message, pop)

    async def wait_session(self):
        while True:
            now = datetime.now()
            if now.weekday() < 5 and self.start <= now.time() < self.end:
                return
            nxt = datetime.combine(now.date(), self.start)
            if now.time() >= self.start:
                nxt += timedelta(days=1)
            log.info("時間外。%s まで待機", nxt.strftime("%m/%d %H:%M"))
            await asyncio.sleep(min(600, max(5, (nxt - now).total_seconds())))

    def in_session(self) -> bool:
        return datetime.now().time() < self.end

    async def ticker(self):
        while True:
            await asyncio.sleep(1)
            await self.emit(self.engine.tick(datetime.now()))

    async def stream(self):
        backoff = 2
        while self.in_session():
            try:
                await asyncio.to_thread(self.client.get_token)
                codes = self.push_codes()
                await asyncio.to_thread(self.client.register, codes)
                await asyncio.to_thread(self.load_limits, codes)
                log.info("PUSH登録 %d銘柄", len(codes))
                async with websockets.connect(self.cfg.ws_url, max_size=None, ping_interval=None) as ws:
                    backoff = 2
                    while self.in_session():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            continue
                        snap = parse_push(json.loads(raw))
                        if snap is None:
                            continue
                        self.recorder.snapshot(snap)
                        await self.emit(self.engine.process(snap))
            except (KabuError, OSError, websockets.WebSocketException) as e:
                log.warning("接続エラー: %s（%d秒後に再接続）", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def scan(self):
        """ランキングを巡回し、PUSH枠を入れ替え、未登録銘柄はランキングの株価でR10・R11を判定する。"""
        sc, first = self.scanner, True
        while self.in_session():
            t0 = asyncio.get_running_loop().time()
            try:
                cands = await asyncio.to_thread(sc.fetch)
                now = datetime.now()
                for c in cands.values():
                    self.engine.add_symbol(SymbolInfo(c.code, c.name, None))
                add, remove = sc.select(cands, now)
                if remove:
                    await asyncio.to_thread(self.client.unregister, remove)
                if add:
                    await asyncio.to_thread(self.client.register_add, add)
                    await asyncio.to_thread(self.load_limits, add)
                if add or remove:
                    log.info("PUSH入替 +%s -%s（ランキング枠 %d/%d）", add, remove, len(sc.active), sc.slots)
                if self.cfg.scanner.light_alerts:
                    pushed = set(sc.push_codes())
                    for c in cands.values():
                        if c.code in pushed or not c.price or not c.prev_close:
                            continue
                        snap = Snapshot(now, c.code, c.price, 0, prev_close=c.prev_close)
                        # 初回は現在の段階を覚えるだけ（起動直後に大量通知しない）
                        await self.emit(self.engine.process_light(snap, silent=first))
                first = False
            except (KabuError, OSError) as e:
                log.warning("ランキング巡回エラー: %s", e)
            wait = self.cfg.scanner.interval_sec - (asyncio.get_running_loop().time() - t0)
            await asyncio.sleep(max(1.0, wait))

    async def run_day(self):
        await self.wait_session()
        self.count = 0
        if self.scanner:
            self.scanner.active.clear()
        groups: dict[str, list[str]] = {}
        for x in self.cfg.symbols:
            groups.setdefault(x.group or "固定", []).append(x.code)
        fixed = " / ".join(f"{g}: {', '.join(c)}" for g, c in groups.items())
        extra = f"＋ランキング枠{self.scanner.slots}" if self.scanner else ""
        await asyncio.to_thread(self.notifier.send, f"kane監視 開始（{fixed}）{extra}")
        tasks = [asyncio.create_task(self.ticker())]
        if self.scanner:
            tasks.append(asyncio.create_task(self.scan()))
        try:
            await self.stream()
        finally:
            for t in tasks:
                t.cancel()
        await asyncio.to_thread(self.notifier.send, f"kane監視 終了（本日の通知 {self.count}件）")

    async def run(self):
        while True:
            await self.run_day()
            await asyncio.sleep(60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.check:
        check(cfg)
        return
    setup_logging(cfg)
    try:
        asyncio.run(Monitor(cfg).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
