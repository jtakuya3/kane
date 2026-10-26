"""baseline（RVOL・年初来最大出来高の基準）の作り方。"""
from datetime import date

from kane.baseline import chart_complete, summarize_rows
from kane.config import _drop_stale

ROWS = [(f"2026/10/{d:02d}", 1000.0 * d) for d in range(1, 24)]


def test_chart_complete_requires_stable_rowcount_and_recent_last_date():
    today = date(2026, 10, 26)
    assert not chart_complete(ROWS, None, today)  # 初回の読み取りでは判断しない
    assert not chart_complete(ROWS, len(ROWS) - 3, today)  # まだ増えている途中
    assert chart_complete(ROWS, len(ROWS), today)
    old = [(f"2026/08/{d:02d}", 100.0) for d in range(1, 32) if d != 30]
    assert not chart_complete(old, len(old), today)  # 8月までしか届いていない表は不採用
    assert not chart_complete(ROWS[:3], 3, today)


def test_drop_stale_disables_ytd_max_only():
    base = {"9656": {"avg_vol": 20000.0, "ytd_max_vol": 23000.0, "ytd_max_date": "2026/08/31", "last_date": "2026/08/31"},
            "4498": {"avg_vol": 500000.0, "ytd_max_vol": 9e6, "ytd_max_date": "2026/10/15", "last_date": "2026/10/23"},
            "7777": {"avg_vol": 1.0, "ytd_max_vol": 2.0, "ytd_max_date": "", "last_date": ""}}
    out = _drop_stale(base, date(2026, 10, 26))
    assert out["9656"]["ytd_max_vol"] is None and out["9656"]["avg_vol"] == 20000.0
    assert out["4498"]["ytd_max_vol"] == 9e6
    assert out["7777"]["ytd_max_vol"] == 2.0  # 古い形式（last_date 無し）はそのまま


def test_summarize_rows_ytd_max_uses_this_year():
    rows = [("2025/12/30", 90000.0)] + ROWS
    r = summarize_rows(rows, year=2026)
    assert r["ytd_max_vol"] == 23000 and r["ytd_max_date"] == "2026/10/23"
