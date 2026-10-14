from datetime import datetime, timedelta

import pandas as pd

from kane.backtest import detect, load_bars, run, turnover_study
from kane.config import RuleConfig, SymbolInfo
from kane.evaluate import AlertRow, PriceBook, evaluate, expected_dir, summarize


def make_bars(tmp_path):
    rows = []
    # 前日：終値1000
    d0 = datetime(2026, 3, 2, 9, 0)
    for i in range(60):
        rows.append(("4498", d0 + timedelta(minutes=i), 1000, 1001, 999, 1000, 1000))
    # 当日：急騰して高値1200、その後失速して下落
    d1 = datetime(2026, 3, 3, 9, 0)
    px = 1000
    for i in range(120):
        if i < 40:
            o, c, v = px, px + 5, 200_000
        elif i < 60:
            o, c, v = px, px, 20_000
        else:
            o, c, v = px, px - 2, 50_000
        rows.append(("4498", d1 + timedelta(minutes=i), o, max(o, c) + 1, min(o, c) - 1, c, v))
        px = c
    df = pd.DataFrame(rows, columns=["銘柄コード", "日時", "始値", "高値", "安値", "終値", "出来高"])
    p = tmp_path / "min1.parquet"
    df.to_parquet(p)
    return p


def test_detect_japanese_columns():
    m = detect(["日時", "銘柄コード", "始値", "高値", "安値", "終値", "出来高"], "bars", {})
    assert m["time"] == "日時" and m["code"] == "銘柄コード" and m["volume"] == "出来高"


def test_backtest_end_to_end(tmp_path):
    bars = load_bars([str(make_bars(tmp_path))], "bars", {})
    known = {"4498": SymbolInfo("4498", "サイバートラスト", 7_285_800)}
    alerts, book, used = run(bars, RuleConfig(), known, 0.05, None)
    rules = {a.rule for a in alerts}
    assert "R10" in rules and "R1" in rules and "R2" in rules
    rows = evaluate(alerts, book)
    assert rows and all("ret5" in r for r in rows)
    summ = summarize(rows)
    assert any(s["rule"] == "R2" and s["n"] > 0 for s in summ)
    study = turnover_study(used, known)
    assert study[0]["code"] == "4498" and 0 < study[0]["high_vol_share"] <= 1


def test_ticks_to_bars(tmp_path):
    t0 = datetime(2026, 3, 3, 9, 0, 1)
    df = pd.DataFrame({"code": ["4498"] * 4, "time": [t0, t0 + timedelta(seconds=10),
                                                      t0 + timedelta(seconds=70), t0 + timedelta(seconds=80)],
                       "price": [100, 105, 103, 101], "qty": [100, 200, 300, 400]})
    p = tmp_path / "t.csv"
    df.to_csv(p, index=False)
    bars = load_bars([str(p)], "ticks", {})
    assert list(bars["open"]) == [100, 103] and list(bars["high"]) == [105, 103]
    assert list(bars["volume"]) == [300, 700]


def test_evaluate_direction_and_returns():
    book = PriceBook()
    t0 = datetime(2026, 3, 3, 10, 0)
    for i, c in enumerate([100, 99, 98, 97, 96, 95, 94]):
        book.add("X", t0 + timedelta(minutes=i), c + 0.5, c - 0.5, c)
    book.freeze()
    rows = evaluate([AlertRow(t0, "X", "R2", "5%", 100.0)], book)
    assert expected_dir("R2", "5%") == -1
    assert round(rows[0]["ret5"], 4) == -0.04  # 10:05時点で確定済みの最後の足（10:04開始）の終値96
    s = summarize(rows)[0]
    assert s["avg5"] > 0  # 下落を期待して下がったのでプラス


def test_min1_agg_format(tmp_path):
    df = pd.DataFrame({"code": ["13570", "153A0"], "d": [20260310, 20260310], "min1": [549, 562],
                       "n": [349, 10], "pv": [2_249_658_000.0, 3_000_000.0], "vv": [470108.0, 1000.0]})
    p = tmp_path / "min1_0304.parquet"
    df.to_parquet(p)
    bars = load_bars([str(p)], "bars", {})
    assert list(bars["code"]) == ["1357", "153A"]
    assert str(bars["dt"].iloc[0]) == "2026-03-10 09:09:00"
    assert round(bars["close"].iloc[0], 1) == round(2_249_658_000 / 470108, 1)


def test_min5_agg_format(tmp_path):
    df = pd.DataFrame({"code": ["13010"], "d": [20260303], "min5": [153], "n": [2],
                       "pv": [2655000.0], "vv": [500.0]})
    p = tmp_path / "intraday_agg_0304.parquet"
    df.to_parquet(p)
    bars = load_bars([str(p)], "bars", {})
    assert str(bars["dt"].iloc[0]) == "2026-03-03 12:45:00" and bars["close"].iloc[0] == 5310


def test_study_summary_text(tmp_path):
    from kane.backtest import summarize_study
    txt = summarize_study([{"high_vol_share": 0.4, "low_vol_share": 0.9, "high_time": "09:10",
                            "high_float_turnover": None, "low_float_turnover": None}])
    assert "中央値 40%" in txt and "寄り天型" in txt
