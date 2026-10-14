from datetime import datetime, timedelta

from kane.config import ScannerConfig
from kane.scanner import RankingScanner, merge_rankings

NOW = datetime(2026, 10, 15, 10, 0)


def rows(*codes):
    return [{"No": i + 1, "Symbol": c, "SymbolName": c, "CurrentPrice": 1100, "ChangeRatio": 100}
            for i, c in enumerate(codes)]


def test_merge_scores_and_prev_close():
    m = merge_rankings([(1, rows("A", "B")), (6, rows("B"))], {"1": 1.0, "6": 1.2})
    assert m["B"].score > m["A"].score
    assert m["A"].prev_close == 1000


def test_select_fills_slots_and_keeps_pinned_out():
    sc = RankingScanner(None, ScannerConfig(max_push=4, min_hold_sec=600), pinned={"P1", "P2"})
    add, remove = sc.select(merge_rankings([(1, rows("P1", "A", "B", "C"))], {}), NOW)
    assert add == ["A", "B"] and remove == []
    assert sc.push_codes() == ["P1", "P2", "A", "B"]


def test_select_rotates_after_min_hold():
    sc = RankingScanner(None, ScannerConfig(max_push=2, min_hold_sec=600, keep_zone=1.0), pinned=set())
    sc.select(merge_rankings([(1, rows("A", "B"))], {}), NOW)
    # 5分後：A,Bは圏外だが最低保持中なので残す
    add, remove = sc.select(merge_rankings([(1, rows("C", "D"))], {}), NOW + timedelta(minutes=5))
    assert add == [] and remove == []
    # 11分後：入れ替え
    add, remove = sc.select(merge_rankings([(1, rows("C", "D"))], {}), NOW + timedelta(minutes=11))
    assert sorted(add) == ["C", "D"] and sorted(remove) == ["A", "B"]


def test_light_rules_from_ranking_price():
    from kane.config import RuleConfig, SymbolInfo
    from kane.engine import Engine
    from kane.models import Snapshot

    e = Engine([], RuleConfig())
    e.add_symbol(SymbolInfo("9999", "テスト", None))
    s0 = Snapshot(NOW, "9999", 1040, 0, prev_close=1000)
    assert e.process_light(s0, silent=True) == []
    a = e.process_light(Snapshot(NOW + timedelta(seconds=10), "9999", 1060, 0, prev_close=1000))
    assert [x.rule for x in a] == ["R10"] and "5%段階" in a[0].message
