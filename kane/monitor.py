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
from datetime import datetime, time, timedelta

import websockets

from .config import Config, load_config
from .engine import Engine
from .kabu import KabuClient, KabuError, parse_push
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

    async def emit(self, alerts):
        for a in alerts:
            self.count += 1
            self.recorder.alert(a)
            await asyncio.to_thread(self.notifier.send, a.message)

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
                await asyncio.to_thread(self.client.register, [s.code for s in self.cfg.symbols])
                log.info("PUSH登録 %d銘柄", len(self.cfg.symbols))
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

    async def run_day(self):
        await self.wait_session()
        self.count = 0
        names = ", ".join(s.code for s in self.cfg.symbols)
        await asyncio.to_thread(self.notifier.send, f"kane監視 開始（{len(self.cfg.symbols)}銘柄: {names}）")
        tick = asyncio.create_task(self.ticker())
        try:
            await self.stream()
        finally:
            tick.cancel()
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
