"""ランキングAPIで全市場から動いている銘柄を拾い、PUSH配信の50枠を自動で入れ替える。

symbols.csv の銘柄は固定（常に登録）。残りの枠をランキングの点数順に埋める。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from .config import ScannerConfig

log = logging.getLogger("kane")


@dataclass
class Candidate:
    code: str
    name: str
    price: float | None
    prev_close: float | None
    score: float = 0.0


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def merge_rankings(lists: list[tuple[int, list[dict]]], weights: dict) -> dict[str, Candidate]:
    """複数のランキングを、順位が高いほど点数が高くなるよう合算する。"""
    out: dict[str, Candidate] = {}
    for type_, rows in lists:
        w = weights.get(str(type_), 1.0)
        for i, r in enumerate(rows):
            code = str(r.get("Symbol") or "").strip()
            if not code:
                continue
            rank = int(r.get("No") or i + 1)
            c = out.get(code)
            if c is None:
                price = _num(r.get("CurrentPrice"))
                diff, pct = _num(r.get("ChangeRatio")), _num(r.get("ChangePercentage"))
                if price and diff is not None:
                    pc = price - diff
                elif price and pct is not None:
                    pc = price / (1 + pct / 100)
                else:
                    pc = None
                c = out[code] = Candidate(code, str(r.get("SymbolName") or ""), price, pc or None)
            c.score += w * max(0, 51 - rank)
    return out


class RankingScanner:
    def __init__(self, client, cfg: ScannerConfig, pinned: set[str]):
        self.client = client
        self.cfg = cfg
        self.pinned = set(pinned)
        self.active: dict[str, datetime] = {}  # ランキング枠の銘柄 → 入れた時刻

    @property
    def slots(self) -> int:
        return max(0, self.cfg.max_push - len(self.pinned))

    def push_codes(self) -> list[str]:
        return sorted(self.pinned) + sorted(self.active)

    def fetch(self) -> dict[str, Candidate]:
        lists = []
        for type_, ex in self.cfg.rankings:
            try:
                lists.append((int(type_), self.client.ranking(int(type_), ex)))
            except Exception as e:  # 1つ失敗しても他のランキングは使う
                log.warning("ランキング取得失敗 %s/%s: %s", type_, ex, e)
            time.sleep(self.cfg.call_gap_sec)
        return merge_rankings(lists, self.cfg.weights)

    def select(self, cands: dict[str, Candidate], now: datetime) -> tuple[list[str], list[str]]:
        """入れる銘柄と外す銘柄を決める。"""
        ranked = [c.code for c in sorted(cands.values(), key=lambda c: -c.score)
                  if c.code not in self.pinned]
        zone = set(ranked[: int(self.slots * self.cfg.keep_zone)])
        keep = [c for c in self.active
                if c in zone or (now - self.active[c]).total_seconds() < self.cfg.min_hold_sec]
        if len(keep) > self.slots:  # 最低保持の銘柄で埋まりすぎたら点数の低い順に外す
            keep.sort(key=lambda c: -(cands[c].score if c in cands else 0))
            keep = keep[: self.slots]
        free = self.slots - len(keep)
        add = [c for c in ranked if c not in keep][:free]
        remove = [c for c in self.active if c not in keep]
        for c in remove:
            del self.active[c]
        for c in add:
            self.active[c] = now
        return add, remove
