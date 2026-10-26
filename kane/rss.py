"""楽天 マーケットスピードII RSS（Excel）からの読み込み。

kane が Excel にシートを作って RssMarket 関数を書き込み、そのセルの値を定期的に読む。
Excel（RSS接続済み）が起動している Windows で動く。COM には pywin32 を使う。
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .config import RssConfig, SymbolInfo
from .models import Snapshot

WATCH_SHEET = "kane_watch"
SCAN_SHEET = "kane_scan"

BASE_KEYS = ["price", "volume", "vwap", "value", "open", "high", "low", "prev_close", "ytd_high"]


class RssError(RuntimeError):
    pass


def watch_fields(cfg: RssConfig) -> list[tuple[str, str]]:
    """固定監視シートの列（キー, RssMarketの項目名）。板を board_levels 本まで読む。"""
    it = cfg.items
    out = [(k, it[k]) for k in BASE_KEYS if it.get(k)]
    for k in ("bid_sign", "ask_sign", "mkt_buy", "mkt_sell", "cap"):
        if it.get(k):
            out.append((k, it[k]))
    for i in range(1, cfg.board_levels + 1):
        for k in ("bid_price", "bid_qty", "ask_price", "ask_qty"):
            out.append((f"{k}{i}", it[k].format(i=i)))
    return out


def scan_fields(cfg: RssConfig) -> list[tuple[str, str]]:
    """スキャンシートの列。軽くするため板は最良気配1本だけ。"""
    it = cfg.items
    keys = ["price", "volume", "vwap", "value", "high", "prev_close", "ytd_high"]
    out = [(k, it[k]) for k in keys if it.get(k)]
    for k in ("bid_sign", "ask_sign", "cap"):
        if it.get(k):
            out.append((k, it[k]))
    for k in ("bid_price", "bid_qty", "ask_price", "ask_qty"):
        out.append((f"{k}1", it[k].format(i=1)))
    return out


def formula(cfg: RssConfig, code: str, item: str) -> str:
    return f'={cfg.function}("{code}{cfg.code_suffix}","{item}")'


def num(v) -> float | None:
    """セルの値を数値にする。空・文字・Excelのエラー値は None。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        # COM経由のExcelエラー値（#N/A など）は大きな負の整数で返る
        return None if v < -2_000_000_000 else float(v)
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def row_to_snapshot(code: str, fields: list[tuple[str, str]], row, ts: datetime,
                    special_values: list[str], value_unit: float = 1000) -> tuple[Snapshot | None, dict]:
    """シートの1行を Snapshot にする。2つ目の戻り値は年初来高値など Snapshot 以外の値。"""
    raw = {k: v for (k, _), v in zip(fields, row)}
    val = {k: num(v) for k, v in raw.items()}
    extra = {"ytd_high": val.get("ytd_high"), "cap": val.get("cap")}  # cap＝時価総額（RSSの単位のまま）
    price = val.get("price")
    if not price:
        extra["over_limit"] = "超過" in str(raw.get("price") or "")  # 楽天RSSの銘柄数上限（500）を超えた
        return None, extra  # 寄り前・データ未着

    def levels(side: str):
        out = []
        i = 1
        while f"{side}_price{i}" in val:
            p, q = val.get(f"{side}_price{i}"), val.get(f"{side}_qty{i}")
            if p and q:
                out.append((p, q))
            i += 1
        return out

    bids, asks = levels("bid"), levels("ask")
    vwap = val.get("vwap")
    vol, value = val.get("volume"), val.get("value")
    if not vwap and vol and value:
        vwap = value * value_unit / vol  # 売買代金（千円）÷ 出来高

    def sign(key):
        s = raw.get(key)
        if s is None:
            return None  # 項目が設定されていない
        s = str(s).strip()
        return "0102" if s in special_values else s  # "" ＝ 特別気配ではない（通常）

    snap = Snapshot(
        ts=ts, symbol=code, price=price, volume=val.get("volume") or 0.0,
        vwap=vwap, high=val.get("high"), low=val.get("low"), open=val.get("open"),
        prev_close=val.get("prev_close"),
        buy5=sum(q for _, q in bids[:5]) or None, sell5=sum(q for _, q in asks[:5]) or None,
        bid=bids[0][0] if bids else None, ask=asks[0][0] if asks else None,
        buy1_qty=bids[0][1] if bids else None, sell1_qty=asks[0][1] if asks else None,
        buy1_sign=sign("bid_sign"), sell1_sign=sign("ask_sign"),
        board_buy=bids if len(bids) > 1 else None, board_sell=asks if len(asks) > 1 else None,
        mkt_buy=val.get("mkt_buy"), mkt_sell=val.get("mkt_sell"),
    )
    return snap, extra


def select_scan(universe: list[SymbolInfo], n: int) -> list[SymbolInfo]:
    """スキャン銘柄を n 個に絞る。平均売買代金（平均出来高×直近終値、baseline）が大きい順。
    baseline の無い銘柄は後ろ。n 以下なら全部。元の並び（コード順）は、選んだあとに戻す。"""
    if len(universe) <= n:
        return universe

    def key(s):
        if s.avg_vol and s.last_close:
            return (0, -(s.avg_vol * s.last_close))
        if s.avg_vol:
            return (1, -s.avg_vol)
        return (2, 0)

    chosen = {s.code for s in sorted(universe, key=key)[:n]}
    return [s for s in universe if s.code in chosen]


def load_universe(path: Path, exclude: set[str], limit: int) -> list[SymbolInfo]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip()
            if code and not code.startswith("#") and code not in exclude:
                out.append(SymbolInfo(code, (r.get("name") or "").strip(), None))
    return out[:limit]


BUSY = (-2147418111, -2147417846)  # Excelが計算中などで呼び出しを拒否した（しばらくすれば通る）


def com_retry(fn, *args, tries: int = 240, wait: float = 0.5):
    """Excelが「呼び出し先が呼び出しを拒否しました」を返したら、待って同じ操作をやり直す。"""
    import time

    for i in range(tries):
        try:
            return fn(*args)
        except Exception as e:
            code = getattr(e, "hresult", None) or (e.args[0] if e.args else None)
            if code not in BUSY or i == tries - 1:
                raise
            time.sleep(wait)


class ExcelRss:
    """起動中の Excel にシートを作って RSS 関数を書き込み、値を読む。"""

    def __init__(self, cfg: RssConfig, workbook: Path):
        self.cfg = cfg
        self.path = workbook
        self.wb = None

    def connect(self):
        try:
            import pythoncom
            import win32com.client
        except ImportError as e:
            raise RssError("pywin32 が入っていません。scripts\\install.bat を実行してください") from e
        pythoncom.CoInitialize()
        try:
            xl = win32com.client.GetActiveObject("Excel.Application")
        except Exception as e:
            raise RssError("Excelが起動していません。マーケットスピードIIにログインし、ExcelでRSSに接続してから起動してください") from e
        target = str(self.path.resolve())
        for wb in xl.Workbooks:
            if str(wb.FullName).lower() == target.lower():
                self.wb = wb
                return
        if self.path.exists():
            self.wb = xl.Workbooks.Open(target)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.wb = xl.Workbooks.Add()
            self.wb.SaveAs(target, 51)  # 51 = .xlsx

    def _sheet(self, name: str):
        """シートを名前で取る（無ければ作る）。Excel が忙しいときの例外は com_retry 側で再試行する。"""
        try:
            return self.wb.Worksheets(name)
        except Exception as e:
            code = getattr(e, "hresult", None) or (e.args[0] if e.args else None)
            if code in BUSY:
                raise
            # 「見つからない」（BADINDEX）→ 作る。同名が既にある（別プロセスが直前に作った）場合は取り直す
        ws = self.wb.Worksheets.Add()
        try:
            ws.Name = name
            return ws
        except Exception:
            try:
                self.wb.Application.DisplayAlerts = False
                ws.Delete()
            finally:
                self.wb.Application.DisplayAlerts = True
            return self.wb.Worksheets(name)

    def setup(self, name: str, codes: list[str], fields: list[tuple[str, str]]):
        """1行目に項目名、A列に銘柄コード、残りに RssMarket の式を書き込む。"""
        ws = com_retry(self._sheet, name)
        com_retry(lambda: ws.Cells.Clear())
        header = ["code"] + [item for _, item in fields]
        rows = [header] + [[c] + [formula(self.cfg, c, item) for _, item in fields] for c in codes]

        def write():
            ws.Range(ws.Cells(1, 1), ws.Cells(len(rows), len(header))).Formula = rows
        com_retry(write)

    def read(self, name: str, nrows: int, ncols: int):
        """データ部分（ヘッダーを除く nrows 行 × 項目 ncols 列）を読む。"""
        ws = com_retry(self._sheet, name)
        if nrows == 0:
            return []
        v = com_retry(lambda: ws.Range(ws.Cells(2, 2), ws.Cells(nrows + 1, ncols + 1)).Value)
        if nrows == 1 and ncols == 1:
            return [[v]]
        if nrows == 1:
            return [list(v[0])] if isinstance(v[0], tuple) else [list(v)]
        return [list(r) for r in v]
