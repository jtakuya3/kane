"""楽天RSS版のライブ監視：Excelのセルを定期的に読み → ルール判定 → Slack通知＋CSV保存。

config.toml の [source] type = "rss" のとき kane.monitor から呼ばれる。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from .config import Config
from .engine import Engine
from .rss import SCAN_SHEET, WATCH_SHEET, ExcelRss, RssError, load_universe, row_to_snapshot, scan_fields, watch_fields
from .sinks import Notifier, Recorder

log = logging.getLogger("kane")


def _hm(s: str):
    h, m = s.split(":")
    return datetime.now().replace(hour=int(h), minute=int(m), second=0, microsecond=0).time()


class RssMonitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        r = cfg.rss
        wb = Path(r.workbook)
        self.rss = ExcelRss(r, wb if wb.is_absolute() else cfg.base_dir / wb)
        self.notifier = Notifier(cfg.slack_webhook_file, cfg.slack_enabled, cfg.beep)
        self.recorder = Recorder(cfg.data_dir, cfg.record_snapshots)
        self.watch = list(cfg.symbols)
        self.pinned = {s.code for s in self.watch}
        self.scan = load_universe(cfg.base_dir / r.universe_csv, self.pinned, r.max_scan)
        self.wf, self.sf = watch_fields(r), scan_fields(r)
        self.engine = Engine(self.watch + self.scan, cfg.rules, on_bar=self.recorder.bar)
        self.infos = {s.code: s for s in self.watch + self.scan}
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.last: dict[str, tuple] = {}
        self.ytd_done: set[str] = set()
        self.count = 0

    # ---- 準備 ----
    def setup_sheets(self):
        self.rss.connect()
        self.rss.setup(WATCH_SHEET, [s.code for s in self.watch], self.wf)
        if self.scan:
            self.rss.setup(SCAN_SHEET, [s.code for s in self.scan], self.sf)
        log.info("RSSシート準備：固定%d銘柄（%d列） / スキャン%d銘柄（%d列）",
                 len(self.watch), len(self.wf), len(self.scan), len(self.sf))

    def check(self, wait_sec: float = 8):
        self.setup_sheets()
        print(f"RSSの式を書き込みました。{wait_sec:.0f}秒待って値を読みます…")
        time.sleep(wait_sec)
        rows = self.rss.read(WATCH_SHEET, len(self.watch), len(self.wf))
        for s, row in list(zip(self.watch, rows))[:3]:
            print(f"\n=== {s.code} {s.name} ===")
            for (key, item), v in zip(self.wf[:12], row[:12]):
                print(f"  {item:<14} → {v!r}")
        bad = sorted({item for row in rows for (k, item), v in zip(self.wf, row)
                      if isinstance(v, int) and v < -2_000_000_000})
        if bad:
            print("\nエラーになった項目（項目名が違う可能性。config.toml の [rss.items] で直せます）:", bad)
        if self.scan:
            srows = self.rss.read(SCAN_SHEET, len(self.scan), len(self.sf))
            got = sum(1 for r in srows if r and r[0] not in (None, ""))
            print(f"\nスキャン：{len(self.scan)}銘柄中 {got}銘柄で現在値を取得")
        print("Slack:", "設定あり" if self.notifier.url else "未設定（画面表示のみ）")

    # ---- 通知 ----
    def emit(self, alerts, snap_by_code):
        for a in alerts:
            if a.symbol not in self.pinned:
                s = snap_by_code.get(a.symbol)
                value = (s.volume * (s.vwap or s.price)) if s else 0
                if a.rule not in self.cfg.rss.scan_rules or value < self.cfg.rss.scan_min_value_yen:
                    continue
            self.count += 1
            self.recorder.alert(a)
            pop = a.rule in self.cfg.popup_rules or f"{a.rule}:{a.level}" in self.cfg.popup_rules
            self.pool.submit(self.notifier.send, a.message, pop)

    # ---- 1回分の読み取り ----
    def poll(self):
        now = datetime.now()
        snaps = {}
        alerts = []
        for sheet, infos, fields, record in (
            (WATCH_SHEET, self.watch, self.wf, True),
            (SCAN_SHEET, self.scan, self.sf, False),
        ):
            if not infos:
                continue
            rows = self.rss.read(sheet, len(infos), len(fields))
            for info, row in zip(infos, rows):
                key = tuple(row)
                if self.last.get(info.code) == key:
                    continue  # 変化なし
                self.last[info.code] = key
                snap, extra = row_to_snapshot(info.code, fields, row, now, self.cfg.rss.special_values)
                if info.code not in self.ytd_done and extra.get("ytd_high"):
                    # 最初に読めた年初来高値（寄り前なら前日までの値）を基準にする
                    if info.ytd_high is None:
                        info.ytd_high = extra["ytd_high"]
                    self.ytd_done.add(info.code)
                if snap is None:
                    continue
                snaps[info.code] = snap
                if record:
                    self.recorder.snapshot(snap)
                alerts += self.engine.process(snap)
        alerts += self.engine.tick(now)
        self.emit(alerts, snaps)

    # ---- メインループ ----
    def run(self):
        start, end = _hm(self.cfg.session_start), _hm(self.cfg.session_end)
        waiting = False
        while True:
            now = datetime.now()
            if not (now.weekday() < 5 and start <= now.time() < end):
                if not waiting:
                    log.info("時間外。%s〜%s の取引時間まで待機します", self.cfg.session_start, self.cfg.session_end)
                    waiting = True
                time.sleep(30)
                continue
            waiting = False
            try:
                self.setup_sheets()
            except Exception as e:
                log.warning("Excel/RSSに接続できません: %s（30秒後に再試行）", e)
                time.sleep(30)
                continue
            self.count = 0
            self.notifier.send(f"kane監視（楽天RSS）開始：固定{len(self.watch)}銘柄＋スキャン{len(self.scan)}銘柄")
            while datetime.now().time() < end:
                t0 = time.monotonic()
                try:
                    self.poll()
                except Exception as e:  # Excelが閉じられた等
                    log.warning("RSS読み取りエラー: %s（再接続します）", e)
                    time.sleep(10)
                    try:
                        self.setup_sheets()
                    except Exception as e2:
                        log.warning("再接続失敗: %s", e2)
                    continue
                time.sleep(max(0.05, self.cfg.rss.poll_sec - (time.monotonic() - t0)))
            self.notifier.send(f"kane監視（楽天RSS）終了（本日の通知 {self.count}件）")
            time.sleep(60)
