from datetime import datetime, timedelta

from kane.config import RuleConfig, SymbolInfo
from kane.engine import Engine
from kane.models import Snapshot

T0 = datetime(2026, 10, 15, 9, 0, 0)


def eng(float_shares=1_000_000, vol5m=None, **rules):
    return Engine([SymbolInfo("TEST", "テスト", float_shares, vol5m)], RuleConfig(**rules))


def snap(sec, price, vol, vwap=None, high=None, buy5=None, sell5=None):
    return Snapshot(T0 + timedelta(seconds=sec), "TEST", price, vol, vwap=vwap or price,
                    high=high, buy5=buy5, sell5=sell5)


def run(e, snaps):
    out = []
    for s in snaps:
        out += e.tick(s.ts)
        out += e.process(s)
    return out


def rules_of(alerts, rule):
    return [a for a in alerts if a.rule == rule]


def test_bars_built_from_cumulative_volume():
    e = eng()
    run(e, [snap(0, 100, 1000), snap(30, 102, 1500), snap(61, 101, 1800), snap(125, 99, 2000)])
    bars = list(e.states["TEST"].bars)
    assert [(b.open, b.high, b.close, b.volume) for b in bars] == [(100, 102, 102, 500), (101, 101, 101, 300)]


def test_r1_turnover_fires_once_per_level():
    e = eng()
    a = run(e, [snap(0, 100, 0), snap(1, 100, 400_000), snap(2, 100, 600_000), snap(3, 100, 910_000)])
    assert [x.level for x in rules_of(a, "R1")] == ["40%", "90%"]


def test_r2_vwap_dev_rearms_after_falling_back():
    e = eng()
    a = run(e, [snap(0, 106, 0, vwap=100), snap(1, 107, 0, vwap=100),
                snap(2, 102, 0, vwap=100), snap(3, 106, 0, vwap=100)])
    assert [x.level for x in rules_of(a, "R2")] == ["5%", "5%"]


def test_r4_double_top_on_weak_volume():
    e = eng(float_shares=None)
    s = [snap(0, 1000, 0, high=1000)]
    vol = 0
    for i in range(1, 6):  # 大商いで高値1100へ
        vol += 100_000
        s.append(snap(i * 60, 1000 + i * 20, vol))
    for i in range(6, 12):  # 3%押す
        vol += 5_000
        s.append(snap(i * 60, 1065, vol))
    for i in range(12, 14):  # 薄商いで再接近
        vol += 5_000
        s.append(snap(i * 60, 1095, vol))
    a = run(e, s)
    assert len(rules_of(a, "R4")) == 1


def test_r9_breakout_with_volume_only():
    e = eng(float_shares=None, vol5m=50_000, breakout_quiet_bars=3)
    s, vol = [], 0
    prices = [1000, 1050, 1020, 1010, 1015, 1020, 1030]
    for i, p in enumerate(prices):
        vol += 1_000
        s.append(snap(i * 60, p, vol))
    s.append(snap(len(prices) * 60, 1060, vol + 60_000))
    a = run(e, s)
    assert len(rules_of(a, "R9")) == 1


def test_recorder_and_replay_roundtrip(tmp_path):
    from kane.config import Config
    from kane.replay import replay
    from kane.sinks import Recorder

    rec = Recorder(tmp_path)
    for x in [snap(0, 100, 0), snap(1, 100, 500_000), snap(61, 101, 900_000)]:
        rec.snapshot(x)
    rec.snaps.close()
    cfg = Config("", "", tmp_path, None, False, False, tmp_path,
                 [SymbolInfo("TEST", "テスト", 1_000_000, None)], "08:55", "15:35", True, RuleConfig())
    alerts = replay(cfg, tmp_path / "snapshots_20261015.csv")
    assert [a.level for a in alerts if a.rule == "R1"] == ["40%", "90%"]


def test_r10_price_step_and_ytd_high():
    e = Engine([SymbolInfo("4382", "ＨＥＲＯＺ", None, issued_shares=17_780_000, ytd_high=1460)], RuleConfig())

    def s(sec, price):
        return Snapshot(T0 + timedelta(seconds=sec), "4382", price, 0, prev_close=1398)

    a = run(e, [s(0, 1420), s(1, 1455), s(2, 1468), s(3, 1470), s(4, 1540), s(5, 1300)])
    r10 = rules_of(a, "R10")
    assert [x.level for x in r10] == ["5%段階", "10%段階", "−5%段階"]
    assert r10[0].message.splitlines()[1:4] == [
        "4382ＨＥＲＯＺ時価総額 261億円",
        "年初来高値更新株価 1468円 前日比 +70円（+5.01%）",
        "直前基準 1398円比 +5.01%  5%段階",
    ]


def board_snap(sec, buy, sell, price=2000):
    return Snapshot(T0.replace(minute=5) + timedelta(seconds=sec), "TEST", price, 0,
                    board_buy=buy, board_sell=sell)


NORMAL_BUY = [(2000 - i, 1000 + i * 100) for i in range(10)]
NORMAL_SELL = [(2001 + i, 1500 + i * 100) for i in range(10)]


def test_r13_big_board_appears():
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    wall_sell = list(NORMAL_SELL)
    wall_sell[3] = (2004, 30_000)  # 急に3万株の売り板
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, wall_sell),
                board_snap(2, NORMAL_BUY, wall_sell)])
    r13 = rules_of(a, "R13")
    assert len(r13) == 1 and r13[0].level == "売り"
    assert "大口売り板 2004円 30,000株（約6,012万円）" in r13[0].message


def test_r13_ignores_existing_wall_and_startup_and_small_amount():
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    wall_buy = list(NORMAL_BUY)
    wall_buy[2] = (1998, 30_000)
    a = run(e, [board_snap(0, wall_buy, NORMAL_SELL), board_snap(1, wall_buy, NORMAL_SELL)])
    assert not rules_of(a, "R13")  # 起動時からあった板
    cheap = [(p / 20, q) for p, q in NORMAL_BUY]
    cheap_wall = list(cheap)
    cheap_wall[1] = (cheap[1][0], 30_000)  # 100円×3万株=300万円未満
    e2 = eng(float_shares=None, wall_min_yen=3_000_000)
    a = run(e2, [board_snap(0, cheap, NORMAL_SELL, 100), board_snap(1, cheap_wall, NORMAL_SELL, 100)])
    assert not rules_of(a, "R13")


def test_board_roundtrip_encoding():
    from kane.sinks import decode_board, encode_board
    assert decode_board(encode_board([(2000.0, 100.0)], [(2001.5, 300.0)])) == ([(2000.0, 100.0)], [(2001.5, 300.0)])


def test_r14_stop_high_lifecycle():
    e = Engine([SymbolInfo("3909", "ショーケース", None)], RuleConfig())

    def s(sec, price, bid, qty, ask=None, sell_qty=None):
        return Snapshot(T0 + timedelta(seconds=sec), "3909", price, 0, prev_close=469,
                        bid=bid, buy1_qty=qty, ask=ask, sell1_qty=sell_qty)

    a = run(e, [
        s(0, 540, 540, 1000, 541, 500),
        s(10, 549, 549, 20_000),            # 張り付き（上限 469+80=549）
        s(20, 549, 549, 18_000),
        s(30, 549, 549, 9_000, 549, 3_000),  # 買い残がピークの半分以下 → 警戒
        s(40, 545, 545, 2_000, 546, 800),   # 剥がれ
        s(50, 549, 549, 5_000),             # 再張り付き
    ])
    r14 = rules_of(a, "R14")
    assert [x.level for x in r14] == ["張り付き", "警戒", "剥がれ", "張り付き"]
    assert "再張り付き" in r14[3].message
    assert "上限 549円から-0.73%" in r14[2].message


def test_upper_limit_table():
    from kane.rules import upper_limit
    assert upper_limit(469) == 549 and upper_limit(1398) == 1698 and upper_limit(99) == 129


def test_r13_default_requires_50m_yen():
    e = eng(float_shares=None)
    wall_sell = list(NORMAL_SELL)
    wall_sell[3] = (2004, 20_000)  # 約4,008万円 → 出ない
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, wall_sell)])
    assert not rules_of(a, "R13")
    wall_sell[4] = (2005, 30_000)  # 別の値段に約6,015万円 → 出る
    a = run(e, [board_snap(2, NORMAL_BUY, wall_sell)])
    assert len(rules_of(a, "R13")) == 1


def test_r13_ignores_wall_scrolling_into_view():
    """株価が動いて、前からあった大口板が見える範囲に入ってきただけなら通知しない。"""
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    # 売り板を2円上にずらす：前の範囲(1991〜2010)の外にある2011円の3万株が新たに見える
    shifted_sell = [(2003 + i, 1500 + i * 100) for i in range(9)] + [(2011, 30_000)]
    shifted_buy = [(2002 - i, 1000 + i * 100) for i in range(10)]
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, shifted_buy, shifted_sell, 2002)])
    assert not rules_of(a, "R13")
