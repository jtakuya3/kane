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
    assert len(scan_fields(cfg)) == 12  # 時価総額（cap）を含む
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
                 source="rss", base_dir=tmp_path, feed=False)
    m = RssMonitor(cfg)
    assert [s.code for s in m.scan] == ["9999"]  # 固定銘柄は除外
    sent = []
    m.pool.submit = lambda f, *a: sent.append(a[0])
    small = Snapshot(TS, "9999", 100, 1000)  # 売買代金10万円
    big = Snapshot(TS, "9999", 1000, 200_000)  # 2億円
    m.emit([Alert(TS, "9999", "R10", "5%段階", "a", 100)], {"9999": small})
    m.emit([Alert(TS, "9999", "R13", "売り", "b", 1000), Alert(TS, "9999", "R10", "買い候補", "c", 1000)], {"9999": big})
    m.emit([Alert(TS, "4498", "R2", "5%", "d", 1000)], {})
    assert sent == ["c", "d"]


def test_vwap_from_value_when_missing():
    cfg = RssConfig(board_levels=0)
    wf = watch_fields(cfg)
    vals = {"price": 2066, "volume": 1000, "vwap": "", "value": 2_000}  # 千円
    snap, _ = row_to_snapshot("4498", wf, [vals.get(k, "") for k, _ in wf], TS, [])
    assert snap.vwap == 2000


def test_feed_color_keys():
    from kane.feed import color_key
    assert color_key("R13:売り", True) == "important" and color_key("R10:買い候補", False) == "buy"
    assert color_key("R4:WARN", False) == "warn" and color_key("R10:利確警戒", False) == "warn"
    assert color_key("R14:張り付き", False) == "info"


def test_parse_rsschart_table():
    from datetime import date

    from kane.baseline import parse_chart
    table = [("銘柄名称", "市場名称", "足種", "日付", "時刻", "始値", "高値", "安値", "終値", "出来高"),
             ("サイバートラスト", "東証", "日足", "2026/10/10", "", 1800, 1850, 1790, 1840, 3_000_000),
             ("サイバートラスト", "東証", "日足", "2026/10/13", "", 1851, 1972, 1830, 1960, "12,000,000"),
             ("サイバートラスト", "東証", "日足", "2026/10/14", "", 1891, 2237, 1790, 2070, 19_960_800)]
    assert parse_chart(table, date(2026, 10, 14)) == [3_000_000, 12_000_000]


def test_parse_rsschart_rakuten_layout():
    from datetime import date

    from kane.baseline import parse_chart
    t = [("=@RssChart(...) => 取得完了",) + (None,) * 11,
         ("銘柄名称", "市場名称", "足種", "日付", "時刻", "始値", "高値", "安値", "終値", "出来高", None, None),
         ("A", "東証", "日足", "2026/10/13", "", 1, 2, 1, 2, 1000, None, None),
         ("A", "東証", "日足", "2026/10/14", "", 1, 2, 1, 2, 3000, None, None)]
    assert parse_chart(t, date(2026, 10, 14)) == [1000]


def test_baseline_summary_ytd_max():
    from kane.baseline import summarize_rows
    rows = [("2025/12/30", 9_000), ("2026/01/05", 3_000), ("2026/03/02", 8_000), ("2026/10/13", 1_000)]
    r = summarize_rows(rows, 2026)
    assert r["ytd_max_vol"] == 8_000 and r["ytd_max_date"] == "2026/03/02" and r["avg_vol"] == 5_250


def test_load_baseline_old_and_new_format(tmp_path):
    from kane.config import SymbolInfo, apply_baseline, load_baseline
    (tmp_path / "baseline.csv").write_text("code,avg_vol,days,ytd_max_vol,ytd_max_date,updated\n"
                                           "4498,1000,60,9000,2026/03/02,2026-10-14\n9999,500,60,,,x\n")
    b = load_baseline(tmp_path)
    i = apply_baseline(SymbolInfo("4498", "", None), b)
    assert i.avg_vol == 1000 and i.ytd_max_vol == 9000 and i.ytd_max_date == "2026/03/02"
    assert apply_baseline(SymbolInfo("9999", "", None), b).ytd_max_vol is None


def test_com_retry_on_busy():
    from kane.rss import com_retry
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise Exception(-2147418111, "呼び出し先が呼び出しを拒否しました。", None, None)
        return "ok"
    assert com_retry(flaky, wait=0) == "ok" and len(calls) == 3
    import pytest
    with pytest.raises(ValueError):
        com_retry(lambda: (_ for _ in ()).throw(ValueError("x")), wait=0)


def test_write_baseline_keeps_previous(tmp_path):
    from kane.baseline import write_baseline
    p = tmp_path / "baseline.csv"
    p.write_text("code,avg_vol,days,ytd_max_vol,ytd_max_date,updated\n1111,5,60,9,2026/01/05,old\n2222,7,60,,,old\n")
    write_baseline(p, {"2222": [("2026/10/13", 100.0)] * 20})
    text = p.read_text()
    assert "1111,5,60,9,2026/01/05,old" in text and "2222,100,20,100,2026/10/13" in text


def test_line_analyze():
    from kane.line import analyze
    closes = [100.0] * 30 + [140.0, 150.0]
    r = analyze(closes)
    p = r["next"][0.30]
    s24 = sum(closes[-24:])
    assert abs(p / ((s24 + p) / 25) - 1.30) < 1e-9
    assert r["streak"] == 2 and r["after"]["30%ライン"][0] == p


def test_load_symbols_mute_flag(tmp_path):
    from kane.config import load_symbols
    p = tmp_path / "s.csv"
    p.write_text("code,name,group,float_shares,breakout_vol5m,issued_shares,ytd_high,loan,mute\n"
                 "1111,A,x,100,,200,,1,\n2222,B,x,100,,200,,,1\n", encoding="utf-8")
    syms = load_symbols(p)
    assert [s.mute for s in syms] == [False, True]


def test_notifier_shows_event_time_not_display_time(capsys):
    """表示の時刻は「起こった時刻」（読み取り時刻）であって、表示した時刻ではない。"""
    from kane.sinks import Notifier

    n = Notifier(None, False, False)
    pushed = []

    class Feed:
        def push(self, text, rule="", important=False, ts=None):
            pushed.append(ts)

    n.feed = Feed()
    ts = datetime(2026, 10, 23, 9, 31, 7)
    n.send("大口板 出た", True, "R13", ts)
    assert capsys.readouterr().out.startswith("09:31:07 ")
    assert pushed == [ts]


def test_notifier_quiet_after_exceptions():
    """15:25以降は出さないが、quiet_except のルール（R16・R18）は出す。"""
    from datetime import datetime as _dt
    from kane.sinks import Notifier
    import kane.sinks as sinks

    n = Notifier(None, False, False, quiet_after="15:25", quiet_except=["R16", "R18"])
    pushed = []

    class Feed:
        def push(self, text, rule="", important=False, ts=None):
            pushed.append(rule)

    n.feed = Feed()

    class Late(_dt):
        @classmethod
        def now(cls, tz=None):
            return _dt(2026, 10, 24, 15, 40)

    old = sinks.datetime
    sinks.datetime = Late
    try:
        n.send("a", True, "R13:出た")
        n.send("b", True, "R18:買い")
        n.send("c", True, "R16:引け")
    finally:
        sinks.datetime = old
    assert pushed == ["R18:買い", "R16:引け"]


def test_load_config_reads_tdnet_and_cap(tmp_path):
    from pathlib import Path
    from kane.config import load_config
    cfg = load_config(Path(__file__).resolve().parent.parent / "config.toml")
    assert cfg.tdnet.buyback_min_pct == 5.0 and cfg.tdnet.small_max_oku == 300
    assert cfg.rss.items["cap"] == "時価総額" and "R18" in cfg.quiet_except
    assert ("cap", "時価総額") in scan_fields(cfg.rss)
