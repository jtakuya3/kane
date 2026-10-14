"""kabuステーションAPI（REST＋PUSH配信）のクライアント。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from .models import Snapshot

# localhost向けなのでWindowsのプロキシ設定を無視する
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class KabuError(RuntimeError):
    pass


class KabuClient:
    def __init__(self, base_url: str, password_file: Path):
        self.base_url = base_url.rstrip("/")
        self.password_file = password_file
        self.token: str | None = None

    def _req(self, method: str, path: str, body=None, auth=True):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if auth:
            req.add_header("X-API-KEY", self.token or "")
        try:
            with _opener.open(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise KabuError(f"{method} {path} -> {e.code} {e.read().decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            raise KabuError(f"{method} {path} -> 接続できません（kabuステーションは起動していますか？）: {e.reason}") from e

    def get_token(self) -> str:
        pw = self.password_file.read_text(encoding="utf-8").strip()
        res = self._req("POST", "/token", {"APIPassword": pw}, auth=False)
        if res.get("ResultCode") != 0 or "Token" not in res:
            raise KabuError(f"トークン取得失敗: {res}")
        self.token = res["Token"]
        return self.token

    def register(self, codes: list[str], exchange: int = 1):
        if len(codes) > 50:
            raise KabuError("PUSH配信の登録は50銘柄までです")
        self._req("PUT", "/unregister/all", {})
        return self._req("PUT", "/register",
                         {"Symbols": [{"Symbol": c, "Exchange": exchange} for c in codes]})

    def board(self, code: str, exchange: int = 1) -> dict:
        return self._req("GET", f"/board/{code}@{exchange}")


def _qty_sum(msg: dict, side: str, n: int = 5) -> float | None:
    total, seen = 0.0, False
    for i in range(1, n + 1):
        lv = msg.get(f"{side}{i}") or {}
        q = lv.get("Qty")
        if q:
            total += q
            seen = True
    return total if seen else None


def parse_push(msg: dict, ts: datetime | None = None) -> Snapshot | None:
    """PUSH配信（/board と同じ形式）を Snapshot に変換する。"""
    price = msg.get("CurrentPrice")
    if not price or not msg.get("Symbol"):
        return None
    sell1 = msg.get("Sell1") or {}
    buy1 = msg.get("Buy1") or {}
    return Snapshot(
        ts=ts or datetime.now(),
        symbol=str(msg["Symbol"]),
        price=float(price),
        volume=float(msg.get("TradingVolume") or 0),
        vwap=msg.get("VWAP") or None,
        high=msg.get("HighPrice") or None,
        low=msg.get("LowPrice") or None,
        open=msg.get("OpeningPrice") or None,
        prev_close=msg.get("PreviousClose") or None,
        buy5=_qty_sum(msg, "Buy"),
        sell5=_qty_sum(msg, "Sell"),
        bid=buy1.get("Price") or None,
        ask=sell1.get("Price") or None,
    )
