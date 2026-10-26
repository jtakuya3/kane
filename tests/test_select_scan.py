"""楽天RSSの銘柄数上限（500）に合わせたスキャン銘柄の選別。"""
from kane.config import SymbolInfo
from kane.rss import select_scan, row_to_snapshot, scan_fields
from kane.config import RssConfig
from datetime import datetime


def mk(code, avg=None, close=None):
    s = SymbolInfo(code, code, None, None, avg_vol=avg)
    s.last_close = close
    return s


def test_select_scan_prefers_turnover_then_volume_then_rest():
    u = [mk("1000", 1000, 100), mk("2000", 50000, 10), mk("3000", 2000, 5000), mk("4000"), mk("5000", 300000, None)]
    out = select_scan(u, 3)
    assert [s.code for s in out] == ["1000", "2000", "3000"]  # 売買代金のある3つが先。終値無し（5000）は後ろ
    assert [s.code for s in select_scan(u, 10)] == ["1000", "2000", "3000", "4000", "5000"]


def test_over_limit_cell_is_flagged():
    cfg = RssConfig()
    cfg.items["bid_sign"] = cfg.items["ask_sign"] = ""
    sf = scan_fields(cfg)
    row = ["表示銘柄数超過"] * len(sf)
    snap, extra = row_to_snapshot("8123", sf, row, datetime(2026, 10, 26, 13, 50), cfg.special_values)
    assert snap is None and extra["over_limit"]
    snap, extra = row_to_snapshot("8123", sf, [""] * len(sf), datetime(2026, 10, 26, 8, 50), cfg.special_values)
    assert snap is None and not extra["over_limit"]
