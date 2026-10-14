from datetime import datetime, timedelta

import pandas as pd

from kane.backtest import detect, load_bars, run, turnover_study
from kane.config import RuleConfig, SymbolInfo
from kane.evaluate import AlertRow, PriceBook, evaluate, expected_dir, summarize


def make_bars(tmp_path):
    rows = []
    days = pd.bdate_range("2026-01-05", periods=26)
    for d in days[:-1]:  # 平常日：株価1000円、1分1,000株（1日6万株）
        for i in range(60):
            rows.append(("4498", d + timedelta(hours=9, minutes=i), 1000, 1001, 999, 1000, 1000))
    px = 1000
    for i in range(60):  # 最終日：1分5,000株（RVOL約5倍）で上昇し、年初来高値1001を更新
        o, c = px, px + 4
        rows.append(("4498", days[-1] + timedelta(hours=9, minutes=i), o, c + 1, o - 1, c, 5000))
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
    r10 = [a for a in alerts if a.rule == "R10"]
    assert [a.level for a in r10][:1] == ["買い候補"]
    rows = evaluate(alerts, book)
    assert rows and all("ret5" in r for r in rows)
    summ = summarize(rows)
    assert any(s["rule"] == "R10" and s["level"] == "買い候補" for s in summ)
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
    df = pd.DataFrame({"code": ["13570", "153A0", "25935"], "d": [20260310] * 3, "min1": [549, 562, 562],
                       "n": [349, 10, 1], "pv": [2_249_658_000.0, 3_000_000.0, 100_000.0],
                       "vv": [470108.0, 1000.0, 100.0]})
    p = tmp_path / "min1_0304.parquet"
    df.to_parquet(p)
    bars = load_bars([str(p)], "bars", {})
    assert sorted(bars["code"]) == ["1357", "153A", "25935"]  # 末尾0以外は別銘柄として5桁のまま
    b = bars.set_index("code")
    assert str(b.loc["1357", "dt"]) == "2026-03-10 09:09:00"
    assert round(b.loc["1357", "close"], 1) == round(2_249_658_000 / 470108, 1)


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


def test_rvol_buckets_and_compute():
    from kane.backtest import compute_rvol, group_label, rvol_bucket

    rows = []
    days = pd.bdate_range("2026-01-05", periods=25)
    for i, d in enumerate(days):
        for k in range(3):
            v = 1000 if i < 24 else 10_000  # 最終日だけ10倍
            rows.append(("4498", d + pd.Timedelta(hours=9, minutes=5 * k), 100, 100, 100, 100, v))
    bars = pd.DataFrame(rows, columns=["code", "dt", "open", "high", "low", "close", "volume"])
    last = days[-1].date()
    rv = compute_rvol(bars, {("4498", last)})
    t = (days[-1] + pd.Timedelta(hours=9, minutes=10)).to_pydatetime()
    assert round(rv[("4498", t)], 1) == 10.0
    assert rvol_bucket(10.0) == "10〜20倍" and rvol_bucket(60) == "50倍以上" and rvol_bucket(None).startswith("不明")
    assert group_label("R10", "30%段階") == "+25%以上の段階" and group_label("R10", "−20%段階") == "−15%以下の段階"


def test_period_table_and_daily_rvol(tmp_path):
    from kane.backtest import daily_rvol, period_table
    from kane.evaluate import AlertRow

    t1, t2 = datetime(2026, 1, 10, 10, 0), datetime(2026, 5, 10, 10, 0)
    alerts = [AlertRow(t1, "X", "R10", "買い候補", 100.0), AlertRow(t2, "X", "R10", "買い候補", 100.0)]
    rows = [{"rule": "R10", "level": "買い候補", "dir": 1, "ret30": 0.01, "rvol": 3.0},
            {"rule": "R10", "level": "買い候補", "dir": 1, "ret30": -0.01, "rvol": 3.0}]
    text, recs = period_table(rows, alerts)
    assert "12〜2月" in text and "5〜6月" in text
    assert any(r["period"] == "12〜2月" and r["n"] == 1 and r["avg30"] == 0.01 for r in recs)
    days = pd.bdate_range("2026-01-05", periods=22)
    bars = pd.DataFrame({"code": ["X"] * 22, "dt": days, "volume": [100.0] * 21 + [1000.0]})
    drv = daily_rvol(bars)
    assert round(drv[("X", days[-1].date())], 1) == 10.0


def test_early_study_detects_ignition_next_bar_entry():
    import numpy as np
    import pandas as pd

    from kane.early import study, summary

    rows = []
    days = pd.bdate_range("2026-01-05", periods=40)
    for i, d in enumerate(days):
        for m in range(0, 300, 5):
            mm = m if m < 150 else m + 60
            vol, p = 100_000, 1000.0
            if i == 30 and m >= 30:
                vol, p = (800_000 if m == 30 else 100_000), (1020.0 if m == 30 else 1050.0)
            rows.append(("1111", d + pd.Timedelta(minutes=540 + mm), p, p, p, p, vol))
    bars = pd.DataFrame(rows, columns=["code", "dt", "open", "high", "low", "close", "volume"])
    recs, ctrl, nd = study(bars, 1e6)
    a5 = [r for r in recs if r["variant"] == "A5"]
    assert len(a5) == 1 and a5[0]["time"] == "09:35"
    assert np.isclose(a5[0]["ret_30分"], 0.0)  # 次の足（1050円）で買う → 上昇後なので0%
    assert "A 点火" in summary(recs, ctrl, nd)[0]
