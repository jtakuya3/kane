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
    a = run(e, [snap(0, 100, 0), snap(1, 100, 500_000), snap(2, 100, 600_000), snap(3, 100, 960_000)])
    assert [x.level for x in rules_of(a, "R1")] == ["50%", "80%", "95%"]


def test_r2_vwap_dev_rearms_after_falling_back():
    e = eng()
    a = run(e, [snap(0, 106, 0, vwap=100), snap(1, 107, 0, vwap=100),
                snap(2, 102, 0, vwap=100), snap(3, 106, 0, vwap=100)])
    assert [x.level for x in rules_of(a, "R2")] == ["5%", "5%"]


def test_r5_board_needs_to_persist():
    e = eng(board_sustain_sec=30)
    a = run(e, [snap(0, 100, 0, buy5=500, sell5=1000), snap(10, 100, 0, buy5=500, sell5=1000)])
    assert not rules_of(a, "R5")
    a = run(e, [snap(31, 100, 0, buy5=500, sell5=1000)])
    assert rules_of(a, "R5")[0].level == "weak"


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


def test_r8_arm_then_trigger():
    e = eng(float_shares=100_000)
    s, vol = [], 0
    for i in range(10):  # 平常の足（1本あたり1,000株）
        vol += 1_000
        s.append(snap(i * 60, 1000, vol))
    # 回転率95%付近で大陰線
    s.append(snap(600, 1000, vol + 1_000))
    s.append(snap(650, 970, 96_000))
    s.append(snap(660, 975, 96_100))
    s.append(snap(700, 1001, 96_200))  # 大陰線の高値1000を上抜け
    a = run(e, s)
    assert [x.level for x in rules_of(a, "R8")] == ["ARM", "BUY"]


def test_r7_rebound_three_conditions():
    e = eng(float_shares=None)
    s, vol, t = [], 0, 0

    def bar(o, h, l, c, v):
        nonlocal vol, t
        for p, dv in ((o, v // 4), (h, v // 4), (l, v // 4), (c, v - 3 * (v // 4))):
            vol += dv
            s.append(snap(t, p, vol))
            t += 10
        t = (t // 60 + 1) * 60

    bar(1000, 1100, 1000, 1100, 100_000)  # ピーク出来高
    for p in (1090, 1070, 1050, 1030):
        bar(p + 10, p + 10, p, p, 30_000)
    bar(1030, 1032, 1020, 1025, 10_000)  # 安値1020
    bar(1025, 1030, 1022, 1028, 10_000)  # 安値を更新しない
    bar(1028, 1031, 1023, 1029, 10_000)
    bar(1029, 1045, 1029, 1044, 40_000)  # 前足高値1031を出来高4倍で上抜け
    s.append(snap(t + 1, 1044, vol))
    a = run(e, s)
    assert len(rules_of(a, "R7")) == 1


def test_r6_rsi_reversal():
    e = eng(float_shares=None)
    s, vol = [], 0
    prices = [1000 + i * 10 for i in range(15)] + [1120, 1100, 1080]
    for i, p in enumerate(prices):
        vol += 1_000
        s.append(snap(i * 60, p, vol))
    s.append(snap(len(prices) * 60, 1080, vol))
    a = run(e, s)
    assert len(rules_of(a, "R6")) == 1


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
    assert [a.level for a in alerts if a.rule == "R1"] == ["50%", "80%"]
