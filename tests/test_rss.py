from datetime import datetime

from kane.config import RssConfig
from kane.rss import formula, num, row_to_snapshot, scan_fields, watch_fields
from kane.universe import filter_rows

TS = datetime(2026, 10, 15, 10, 0)


def test_fields_and_formula():
    cfg = RssConfig(board_levels=2)
    wf = watch_fields(cfg)
    assert wf[0] == ("price", "現在値")
    assert ("ask_qty2", "最良売気配数量2") in wf
    assert len(scan_fields(cfg)) == 11
    assert formula(cfg, "4498", "現在値") == '=RssMarket("4498.T","現在値")'


def test_num_handles_errors_and_strings():
    assert num(-2146826246) is None  # #N/A
    assert num("1,234") == 1234 and num("") is None and num(None) is None and num(5) == 5.0


def test_row_to_snapshot_with_board_and_special_quote():
    cfg = RssConfig(board_levels=2)
    cfg.items["bid_sign"] = "最良買気配フラグ"
    wf = watch_fields(cfg)
    vals = {"price": 549, "volume": 646000, "vwap": 530.85, "open": 500, "high": 549, "low": 495,
            "prev_close": 469, "ytd_high": 520, "bid_sign": "特",
            "bid_price1": 549, "bid_qty1": 14300, "ask_price1": "", "ask_qty1": "",
            "bid_price2": 548, "bid_qty2": 1000, "ask_price2": "", "ask_qty2": ""}
    snap, extra = row_to_snapshot("3909", wf, [vals.get(k, "") for k, _ in wf], TS, cfg.special_values)
    assert snap.price == 549 and snap.bid == 549 and snap.buy1_qty == 14300 and snap.ask is None
    assert snap.buy1_sign == "0102" and snap.board_buy == [(549, 14300), (548, 1000)]
    assert extra["ytd_high"] == 520


def test_row_without_price_is_skipped():
    cfg = RssConfig(board_levels=0)
    wf = watch_fields(cfg)
    snap, _ = row_to_snapshot("4498", wf, [""] * len(wf), TS, [])
    assert snap is None


def test_universe_filter():
    rows = [["日付", "コード", "銘柄名", "市場・商品区分"],
            [20260930, 4498.0, "サイバートラスト", "グロース（内国株式）"],
            [20260930, "153A", "カウリス", "グロース（内国株式）"],
            [20260930, 1306.0, "TOPIX連動型", "ETF・ETN"],
            [20260930, 7203.0, "トヨタ", "プライム（内国株式）"]]
    assert filter_rows(rows, ["グロース"]) == [("4498", "サイバートラスト"), ("153A", "カウリス")]


def test_rss_monitor_scan_filter(tmp_path):
    from kane.config import Config, RuleConfig, SymbolInfo
    from kane.models import Alert, Snapshot
    from kane.rss_monitor import RssMonitor

    (tmp_path / "universe.csv").write_text("code,name\n9999,スキャン株\n4498,重複\n", encoding="utf-8")
    cfg = Config("", "", None, None, False, False, tmp_path,
                 [SymbolInfo("4498", "サイバートラスト", 7_285_800)], "08:55", "15:35", False, RuleConfig(),
                 source="rss", base_dir=tmp_path)
    m = RssMonitor(cfg)
    assert [s.code for s in m.scan] == ["9999"]  # 固定銘柄は除外
    sent = []
    m.pool.submit = lambda f, *a: sent.append(a[0])
    small = Snapshot(TS, "9999", 100, 1000)  # 売買代金10万円
    big = Snapshot(TS, "9999", 1000, 200_000)  # 2億円
    m.emit([Alert(TS, "9999", "R10", "5%段階", "a", 100)], {"9999": small})
    m.emit([Alert(TS, "9999", "R2", "5%", "b", 1000), Alert(TS, "9999", "R10", "5%段階", "c", 1000)], {"9999": big})
    m.emit([Alert(TS, "4498", "R2", "5%", "d", 1000)], {})
    assert sent == ["c", "d"]


def test_vwap_from_value_when_missing():
    cfg = RssConfig(board_levels=0)
    wf = watch_fields(cfg)
    vals = {"price": 2066, "volume": 1000, "vwap": "", "value": 2_000_000}
    snap, _ = row_to_snapshot("4498", wf, [vals.get(k, "") for k, _ in wf], TS, [])
    assert snap.vwap == 2000
