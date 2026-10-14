"""通知（Slack・画面・ビープ）と日次CSVの保存。"""
from __future__ import annotations

import csv
import json
import logging
import urllib.request
from datetime import date, datetime
from datetime import time as dtime
from pathlib import Path

from .models import Alert, Bar, Snapshot

log = logging.getLogger("kane")

SNAP_COLS = ["ts", "symbol", "price", "volume", "vwap", "high", "low", "open",
             "prev_close", "buy5", "sell5", "bid", "ask",
             "buy1_qty", "sell1_qty", "buy1_sign", "sell1_sign", "board"]
BAR_COLS = ["start", "symbol", "open", "high", "low", "close", "volume", "turnover", "vwap"]
ALERT_COLS = ["ts", "symbol", "rule", "level", "price", "turnover", "vwap_dev", "message"]


def _popup(text: str):
    """Windowsの最前面メッセージボックス（別スレッドなので監視は止まらない）。"""
    try:
        import ctypes
        import threading

        MB_TOPMOST, MB_SETFOREGROUND, MB_ICONINFO = 0x40000, 0x10000, 0x40
        threading.Thread(
            target=ctypes.windll.user32.MessageBoxW,
            args=(0, text, "kane", MB_TOPMOST | MB_SETFOREGROUND | MB_ICONINFO),
            daemon=True,
        ).start()
    except Exception:
        pass  # Windows以外では何もしない


def encode_board(buy, sell) -> str:
    """板を "値段:数量;…|値段:数量;…"（買い|売り）の文字列にする。"""
    if buy is None and sell is None:
        return ""
    f = lambda lv: ";".join(f"{p:g}:{q:g}" for p, q in (lv or []))
    return f"{f(buy)}|{f(sell)}"


def decode_board(s: str | None):
    if not s or "|" not in s:
        return None, None
    def g(part):
        return [tuple(float(x) for x in kv.split(":")) for kv in part.split(";") if kv]
    b, a = s.split("|", 1)
    return g(b), g(a)


class Notifier:
    def __init__(self, webhook_file: Path | None, enabled: bool, beep: bool,
                 feed: bool = False, dialog: bool = False, quiet_after: str | None = None):
        self.url = None
        if enabled and webhook_file and webhook_file.exists():
            self.url = webhook_file.read_text(encoding="utf-8").strip() or None
        self.beep = beep
        self.dialog = dialog
        self.quiet_after = None  # この時刻以降は画面表示・音・Slackを出さない（記録と黒い画面の表示のみ）
        if quiet_after:
            h, m = quiet_after.split(":")
            self.quiet_after = dtime(int(h), int(m))
        self.feed = None
        if feed:
            from .feed import AlertFeed

            self.feed = AlertFeed()

    def send(self, text: str, popup: bool = False, rule: str = ""):
        """popup=True は重要な通知（アラート窓で赤く強調、dialog 設定時はメッセージボックスも）。"""
        print(f"{datetime.now():%H:%M:%S} {text}", flush=True)
        if self.quiet_after and datetime.now().time() >= self.quiet_after:
            return
        if self.feed:
            self.feed.push(text, rule, popup)
        if popup and self.dialog:
            _popup(text)
        if self.beep:
            try:
                import winsound

                winsound.MessageBeep()
            except Exception:
                pass
        if not self.url:
            return
        try:
            req = urllib.request.Request(self.url, data=json.dumps({"text": text}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:  # 通知失敗で監視を止めない
            log.warning("Slack送信失敗: %s", e)


class DailyCsv:
    """data_dir/<prefix>_YYYYMMDD.csv に追記する。"""

    def __init__(self, data_dir: Path, prefix: str, cols: list[str]):
        self.data_dir, self.prefix, self.cols = data_dir, prefix, cols
        self._day: date | None = None
        self._f = None
        self._w = None

    def write(self, ts: datetime, row: dict):
        if self._day != ts.date():
            self.close()
            self.data_dir.mkdir(parents=True, exist_ok=True)
            path = self.data_dir / f"{self.prefix}_{ts:%Y%m%d}.csv"
            new = not path.exists()
            self._f = open(path, "a", encoding="utf-8", newline="")
            self._w = csv.DictWriter(self._f, fieldnames=self.cols, extrasaction="ignore")
            if new:
                self._w.writeheader()
            self._day = ts.date()
        self._w.writerow(row)
        self._f.flush()

    def close(self):
        if self._f:
            self._f.close()
            self._f = None


class Recorder:
    def __init__(self, data_dir: Path, snapshots: bool = True):
        self.snaps = DailyCsv(data_dir, "snapshots", SNAP_COLS) if snapshots else None
        self.bars = DailyCsv(data_dir, "bars", BAR_COLS)
        self.alerts = DailyCsv(data_dir, "alerts", ALERT_COLS)

    def snapshot(self, s: Snapshot):
        if self.snaps:
            row = {c: getattr(s, c) for c in SNAP_COLS if c != "board"}
            row["board"] = encode_board(s.board_buy, s.board_sell)
            row["ts"] = s.ts.isoformat(timespec="milliseconds")
            self.snaps.write(s.ts, row)

    def bar(self, st, b: Bar):
        self.bars.write(b.start, {
            "start": b.start.isoformat(timespec="minutes"), "symbol": st.info.code,
            "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume,
            "turnover": round(st.turnover, 4) if st.turnover is not None else "",
            "vwap": st.last.vwap if st.last else "",
        })

    def alert(self, a: Alert):
        t, d = a.extras.get("turnover"), a.extras.get("vwap_dev")
        self.alerts.write(a.ts, {
            "ts": a.ts.isoformat(timespec="seconds"), "symbol": a.symbol, "rule": a.rule,
            "level": a.level, "price": a.price,
            "turnover": round(t, 4) if t is not None else "",
            "vwap_dev": round(d, 4) if d is not None else "", "message": a.message,
        })


def read_snapshots(path: Path):
    """snapshots_YYYYMMDD.csv を Snapshot として順に返す（リプレイ用）。"""

    def f(v):
        return float(v) if v not in ("", None) else None

    def t(v):
        return v or None

    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            yield Snapshot(
                ts=datetime.fromisoformat(r["ts"]), symbol=r["symbol"], price=float(r["price"]),
                volume=float(r["volume"]), vwap=f(r["vwap"]), high=f(r["high"]), low=f(r["low"]),
                open=f(r["open"]), prev_close=f(r["prev_close"]), buy5=f(r["buy5"]),
                sell5=f(r["sell5"]), bid=f(r["bid"]), ask=f(r["ask"]),
                buy1_qty=f(r.get("buy1_qty")), sell1_qty=f(r.get("sell1_qty")),
                buy1_sign=t(r.get("buy1_sign")), sell1_sign=t(r.get("sell1_sign")),
                board_buy=decode_board(r.get("board"))[0], board_sell=decode_board(r.get("board"))[1],
            )
