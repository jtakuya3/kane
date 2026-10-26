from datetime import datetime, timedelta

from kane.config import RuleConfig, SymbolInfo
from kane.engine import Engine
from kane.models import Snapshot

T0 = datetime(2026, 10, 15, 9, 0, 0)


FLAT = [[0, 0.0], [1, 1.0], [390, 1.0]]  # テスト用：9:01以降は「1日分が出た」とみなす配分


def eng(float_shares=1_000_000, vol5m=None, avg_vol=None, **rules):
    rules.setdefault("volume_profile", FLAT)
    rules.setdefault("depth_jump_min_yen", 10 ** 12)  # 板の総量の通知は、専用のテスト以外では切る
    return Engine([SymbolInfo("TEST", "テスト", float_shares, vol5m, avg_vol=avg_vol)], RuleConfig(**rules))


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


def board_snap(sec, buy, sell, price=2000):
    return Snapshot(T0.replace(minute=5) + timedelta(seconds=sec), "TEST", price, 0,
                    board_buy=buy, board_sell=sell)


NORMAL_BUY = [(2000 - i, 1000 + i * 100) for i in range(10)]
NORMAL_SELL = [(2001 + i, 1500 + i * 100) for i in range(10)]


def test_r13_big_board_appears():
    e = eng(float_shares=None, wall_min_yen=3_000_000, wall_notify_appear=True)
    wall_sell = list(NORMAL_SELL)
    wall_sell[3] = (2004, 30_000)  # 急に3万株の売り板
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, wall_sell),
                board_snap(2, NORMAL_BUY, wall_sell)])
    r13 = rules_of(a, "R13")
    assert len(r13) == 1 and r13[0].level == "売り"
    assert "大口売り板 2004円 30,000株（約6,012万円）" in r13[0].message


def test_r13_ignores_existing_wall_and_startup_and_small_amount():
    e = eng(float_shares=None, wall_min_yen=3_000_000, wall_notify_appear=True)
    wall_buy = list(NORMAL_BUY)
    wall_buy[2] = (1998, 30_000)
    a = run(e, [board_snap(0, wall_buy, NORMAL_SELL), board_snap(1, wall_buy, NORMAL_SELL)])
    assert not rules_of(a, "R13")  # 起動時からあった板
    cheap = [(p / 20, q) for p, q in NORMAL_BUY]
    cheap_wall = list(cheap)
    cheap_wall[1] = (cheap[1][0], 30_000)  # 100円×3万株=300万円未満
    e2 = eng(float_shares=None, wall_min_yen=3_000_000, wall_notify_appear=True)
    a = run(e2, [board_snap(0, cheap, NORMAL_SELL, 100), board_snap(1, cheap_wall, NORMAL_SELL, 100)])
    assert not rules_of(a, "R13")


def test_r13_default_is_silent_on_appear():
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    wall_sell = list(NORMAL_SELL)
    wall_sell[3] = (2004, 30_000)
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, wall_sell)])
    assert not rules_of(a, "R13")


def test_r13_peel_warning_by_cancel_then_gone():
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    def sell_with(q):
        w = list(NORMAL_SELL)
        w[3] = (2004, q)
        return w
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, sell_with(30_000)),
                board_snap(2, NORMAL_BUY, sell_with(25_000)),
                board_snap(3, NORMAL_BUY, sell_with(14_000)),   # ピークの47% → 予兆
                board_snap(4, NORMAL_BUY, sell_with(12_000)),   # 予兆は1回だけ
                board_snap(5, NORMAL_BUY, sell_with(3_000))])   # 10% → 剥がれ
    r13 = rules_of(a, "R13")
    assert [x.level for x in r13] == ["売り板剥がれ予兆", "売り板剥がれ"]
    assert "ピーク 30,000株 → 14,000株（47%）  上に抜けやすい" in r13[0].message
    assert "取り消し 16,000株" in r13[0].message


def test_r13_wall_eaten_through():
    """最良売り気配の大口売り板が約定で食われ、株価が突き抜ける。"""
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    sell = [(2001, 30_000)] + NORMAL_SELL[1:]
    def s(sec, q, vol, buy=NORMAL_BUY, sell_=None):
        x = board_snap(sec, buy, sell_ or [(2001, q)] + NORMAL_SELL[1:])
        x.volume = vol
        return x
    up_buy = [(2001 - i, 1000) for i in range(10)]
    up_sell = [(2002 + i, 1500) for i in range(10)]
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), s(1, 30_000, 1000), s(2, 12_000, 19_000),
                s(3, 0, 32_000, up_buy, up_sell)])
    r13 = rules_of(a, "R13")
    assert [x.level for x in r13] == ["売り板剥がれ予兆", "売り板剥がれ"]
    assert "約定で食われた 18,000株 / 取り消し 0株" in r13[0].message
    assert "突き抜けた" in r13[1].message


def test_r13_wall_out_of_view_is_dropped_silently():
    e = eng(float_shares=None, wall_min_yen=3_000_000)
    wall_sell = list(NORMAL_SELL)
    wall_sell[9] = (2010, 30_000)
    down_sell = [(1995 + i, 1500) for i in range(10)]  # 株価が下がり、2010円は見えなくなった
    down_buy = [(1994 - i, 1000) for i in range(10)]
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, wall_sell),
                board_snap(2, down_buy, down_sell, 1995)])
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
    e = eng(float_shares=None, wall_notify_appear=True)
    wall_sell = list(NORMAL_SELL)
    wall_sell[3] = (2004, 20_000)  # 約4,008万円 → 出ない
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, NORMAL_BUY, wall_sell)])
    assert not rules_of(a, "R13")
    wall_sell[4] = (2005, 30_000)  # 別の値段に約6,015万円 → 出る
    a = run(e, [board_snap(2, NORMAL_BUY, wall_sell)])
    assert len(rules_of(a, "R13")) == 1


def test_r13_reports_wall_scrolling_into_view():
    """株価が動いて、前からあった大口板が見える範囲に入ってきたときは「見える範囲に入った」として通知する。"""
    e = eng(float_shares=None, wall_min_yen=3_000_000, wall_notify_appear=True)
    # 売り板を2円上にずらす：前の範囲(1991〜2010)の外にある2011円の3万株が新たに見える
    shifted_sell = [(2003 + i, 1500 + i * 100) for i in range(9)] + [(2011, 30_000)]
    shifted_buy = [(2002 - i, 1000 + i * 100) for i in range(10)]
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, shifted_buy, shifted_sell, 2002)])
    r = rules_of(a, "R13")
    assert len(r) == 1 and "見える範囲に入った" in r[0].message and r[0].extras["wall_price"] == 2011


def test_r2_needs_8pct_and_rvol20():
    # 平均日出来高1,000株 → 累計出来高30,000株でRVOL30倍
    e = eng(avg_vol=1_000)
    a = run(e, [snap(60, 106, 30_000, vwap=100), snap(61, 109, 30_000, vwap=100)])
    r2 = rules_of(a, "R2")
    assert [x.level for x in r2] == ["8%"]  # +5%は出さない、+8%は出す
    assert "浮動株回転率 3%" in r2[0].message and "RVOL 30.0倍" in r2[0].message
    e2 = eng(avg_vol=1_000)
    a = run(e2, [snap(60, 109, 5_000, vwap=100)])  # RVOL5倍 → 出さない
    assert not rules_of(a, "R2")


def test_r4_only_with_rvol20():
    def scenario(avg):
        e = eng(float_shares=None, avg_vol=avg)
        s_ = [snap(60, 1000, 0, high=1000)]
        vol = 0
        for i in range(2, 7):
            vol += 100_000
            s_.append(snap(i * 60, 1000 + i * 20, vol))
        for i in range(7, 13):
            vol += 5_000
            s_.append(snap(i * 60, 1065, vol))
        for i in range(13, 15):
            vol += 5_000
            s_.append(snap(i * 60, 1115, vol))
        return rules_of(run(e, s_), "R4")
    assert len(scenario(10_000)) == 1  # 累計約54万株 ÷ 1万株 = 54倍
    assert scenario(1_000_000) == []  # RVOL 0.5倍 → 出さない


def test_r10_buy_candidate_and_fade():
    def e10(avg):
        return Engine([SymbolInfo("4382", "ＨＥＲＯＺ", None, issued_shares=17_780_000, ytd_high=1460,
                                  avg_vol=avg)], RuleConfig(volume_profile=FLAT, buy_alerts=buy))

    buy = False
    assert rules_of(run(e10(10_000), [s0 := Snapshot(T0 + timedelta(seconds=61), "4382", 1468, 50_000,
                                                     prev_close=1398)]), "R10") == []  # 既定では出さない
    buy = True

    def s(sec, price, vol):
        return Snapshot(T0 + timedelta(seconds=sec), "4382", price, vol, prev_close=1398)

    a = run(e10(10_000), [s(60, 1450, 30_000), s(61, 1468, 50_000)])  # RVOL 5倍で年初来高値更新
    r10 = rules_of(a, "R10")
    assert [x.level for x in r10] == ["買い候補"]
    assert "買い候補：年初来高値 1460円を更新 × 出来高5.0倍" in r10[0].message
    assert "4382ＨＥＲＯＺ時価総額 261億円" in r10[0].message
    assert rules_of(run(e10(1_000), [s(60, 1468, 50_000)]), "R10") == []  # RVOL 50倍 → 買い候補は出さない
    a = run(e10(1_000), [s(60, 1750, 50_000)])  # +25%超 × RVOL 50倍 → 利確警戒
    assert [x.level for x in rules_of(a, "R10")] == ["利確警戒"]


def test_r15_ytd_volume_pace_then_record():
    prof = [[0, 0.0], [60, 0.5], [390, 1.0]]  # 10:00までに1日の半分
    e = Engine([SymbolInfo("TEST", "テスト", None, avg_vol=10_000, ytd_max_vol=100_000,
                           ytd_max_date="2026/03/02")], RuleConfig(volume_profile=prof))

    def s(h, m, vol):
        return Snapshot(T0.replace(hour=h, minute=m), "TEST", 1000, vol, vwap=1000, prev_close=950)

    a = run(e, [s(9, 3, 90_000),        # 9:05より前はペース判定しない
                s(10, 0, 40_000),       # 最大日の推定5万株に届かない（出来高が戻ることは実際にはないがテスト用）
                s(10, 0, 50_000),       # 5万株 → 年初来ペース
                s(10, 30, 70_000),      # ペースは1日1回
                s(11, 0, 100_001)])     # 年初来更新
    r15 = rules_of(a, "R15")
    assert [x.level for x in r15] == ["年初来ペース", "年初来更新"]
    assert "今年の最大 100,000株（2026/03/02）" in r15[1].message


def test_r15_record_without_pace_suppresses_later_pace():
    e = Engine([SymbolInfo("TEST", "テスト", None, ytd_max_vol=1_000)], RuleConfig(volume_profile=FLAT))
    a = run(e, [Snapshot(T0.replace(minute=6), "TEST", 100, 2_000), Snapshot(T0.replace(minute=7), "TEST", 100, 3_000)])
    assert [x.level for x in rules_of(a, "R15")] == ["年初来更新"]


def test_r13_ladder_appears_and_disappears():
    """同じ量の板が4段連なって出たら「連なり板」、過半数が消えたら「剥がれ」。"""
    e = eng(float_shares=None, wall_notify_appear=False, ladder_min_yen=20_000_000)
    ladder_buy = [(2000 - i, 1000 + i * 100) for i in range(6)] + [(1994 - i, 10000) for i in range(4)]
    a = run(e, [board_snap(0, NORMAL_BUY, NORMAL_SELL), board_snap(1, ladder_buy, NORMAL_SELL),
                board_snap(2, ladder_buy, NORMAL_SELL)])
    r = rules_of(a, "R13")
    assert len(r) == 1 and r[0].level == "買い連なり板" and r[0].extras["ladder_n"] == 4
    assert "1991〜1994円" in r[0].message and "10,000株×4段" in r[0].message
    gone_buy = [(2000 - i, 1000 + i * 100) for i in range(6)] + [(1994, 10000), (1993, 500), (1992, 300), (1991, 200)]
    a2 = run(e, [board_snap(3, gone_buy, NORMAL_SELL)])
    r2 = rules_of(a2, "R13")
    assert len(r2) == 1 and r2[0].level == "買い連なり板剥がれ"


def test_r13_depth_jump_up_and_down():
    """買い板の総量が1回の更新で30%以上増えたら「急増」、引っ込めたら「急減」。"""
    e = eng(float_shares=None, wall_notify_appear=False, depth_jump_min_yen=10_000_000)
    q = [3000, 9000, 4000, 12000, 5000, 8000, 6000, 11000, 7000, 10000]  # ばらばらの量（連なりにならない）。合計7.5万株
    base_buy = [(2000 - i, q[i]) for i in range(10)]
    jump_buy = list(base_buy)
    jump_buy[8] = (1992, 47_000)  # 奥の段に急に+4万株（+53%）
    a = run(e, [board_snap(0, base_buy, NORMAL_SELL), board_snap(1, jump_buy, NORMAL_SELL)])
    r = rules_of(a, "R13")
    assert [x.level for x in r] == ["買い板急増"]
    assert "1992円 +40,000株" in r[0].message and r[0].extras["depth_delta"] == 40_000
    a2 = run(e, [board_snap(2, base_buy, NORMAL_SELL)])
    r2 = rules_of(a2, "R13")
    assert "買い板急減" in [x.level for x in r2]  # 単独の大口板としての「剥がれ」も同時に出てよい


def test_r16_close_auction_sell_imbalance():
    """引けオークション中に成行売りが買い板合計の30%以上超過したら通知。15:25前は出さない。"""
    from kane.models import Snapshot
    e = eng(float_shares=None, close_cooldown_sec=120)
    def snapc(hh, mm, mb, ms):
        return Snapshot(T0.replace(hour=hh, minute=mm, second=0), "TEST", 3872, 100000,
                        board_buy=[(3872 - i, 5000) for i in range(10)], board_sell=[(3873 + i, 5000) for i in range(10)],
                        mkt_buy=mb, mkt_sell=ms)
    a = run(e, [snapc(15, 20, 1000, 40000), snapc(15, 26, 1000, 40000)])
    r = rules_of(a, "R16")
    assert len(r) == 1 and r[0].level == "引け成行売り超過" and r[0].extras["imbalance"] == 39000
    assert "成行 売り 40,000株 / 買い 1,000株" in r[0].message
    a2 = run(e, [snapc(15, 27, 1000, 41000)])  # 1.5倍未満の増え方は cooldown（120秒）内は黙る
    assert not rules_of(a2, "R16")


def test_r13_depth_move_between_levels():
    """買い板の大口が 1998円 から 1995円 に移動（総量は同じ）→「移動」を通知。"""
    e = eng(float_shares=None, wall_notify_appear=False, depth_jump_min_yen=10_000_000)
    q = [3000, 9000, 4000, 12000, 5000, 8000, 6000, 11000, 7000, 10000]
    base = [(2000 - i, q[i]) for i in range(10)]
    big = list(base); big[2] = (1998, 4000 + 40_000)
    moved = list(base); moved[5] = (1995, 8000 + 40_000)
    a = run(e, [board_snap(0, base, NORMAL_SELL), board_snap(1, big, NORMAL_SELL), board_snap(200, moved, NORMAL_SELL)])
    levels = [x.level for x in rules_of(a, "R13")]
    assert "買い板急増" in levels and "買い板移動" in levels
    mv = [x for x in rules_of(a, "R13") if x.level == "買い板移動"][0]
    assert mv.extras["move_from"] == 1998 and mv.extras["move_to"] == 1995 and "現在値から離した" in mv.message


def test_r17_special_buy_quote_and_release():
    """特買いが付いたら通知（赤）、解消して値が付いたら「特買解消」。付いたままの間は黙る。"""
    from kane.models import Snapshot
    e = eng(float_shares=None)
    def sp(sec, price, sign="", bid=None):  # 通常時はフラグの欄が空（""）、特別気配で "0102"
        return Snapshot(T0.replace(minute=30) + timedelta(seconds=sec), "TEST", price, 10000,
                        bid=bid or price, ask=(bid or price) + 1, buy1_qty=120000, sell1_qty=300,
                        buy1_sign=sign, sell1_sign="")
    a = run(e, [sp(0, 1000), sp(1, 1000, "0102", 1030), sp(2, 1000, "0102", 1060), sp(40, 1090, "")])
    r = rules_of(a, "R17")
    assert [x.level for x in r] == ["特買", "特買解消"]
    assert "特別買い気配 1030円（直前 1000円から +3.0%）" in r[0].message and "120,000株" in r[0].message
    assert r[0].extras["phase"] == "発生" and r[0].extras["base_price"] == 1000
    assert "解消（39秒） → 1090円で値が付いた、特買前 1000円から +9.0%" in r[1].message


def test_r17_special_sell_quote_flicker_is_quiet():
    """特売りが20秒以内に点滅しても2回目は出さない。フラグ項目が無い（None）なら何もしない。"""
    from kane.models import Snapshot
    e = eng(float_shares=None)
    def sp(sec, sign):
        return Snapshot(T0.replace(minute=30) + timedelta(seconds=sec), "TEST", 500, 10000,
                        bid=490, ask=495, buy1_sign="", sell1_sign=sign)
    a = run(e, [sp(0, ""), sp(1, "0102"), sp(5, ""), sp(8, "0102")])
    assert [x.level for x in rules_of(a, "R17")] == ["特売", "特売解消"]  # 8秒後の再発は黙る
    e2 = eng(float_shares=None)
    a2 = run(e2, [Snapshot(T0.replace(minute=30), "TEST", 500, 10000),
                  Snapshot(T0.replace(minute=31), "TEST", 510, 11000)])
    assert not rules_of(a2, "R17")


def test_rvol_ignored_when_baseline_broken():
    """年初来最大＜平均（日足が途中まで）や RVOL が桁外れの基準では、RVOL も R15 も出さない。"""
    from kane.rules import baseline_ok, rvol_of
    from kane.config import SymbolInfo
    bad = SymbolInfo("X", "x", None, None, avg_vol=50000)
    bad.ytd_max_vol, bad.ytd_max_date = 23000, "2026/08/31"
    assert not baseline_ok(bad)
    tiny = SymbolInfo("Y", "y", None, None, avg_vol=10)
    assert baseline_ok(tiny)
    e = Engine([tiny], RuleConfig(volume_profile=FLAT))
    run(e, [Snapshot(T0 + timedelta(minutes=30), "Y", 1000, 120000)])
    st = e.states["Y"]
    assert rvol_of(st, T0 + timedelta(minutes=30), e.rules) is None  # 12,000倍は異常値として捨てる
    e2 = Engine([bad], RuleConfig(volume_profile=FLAT))
    a = run(e2, [Snapshot(T0 + timedelta(minutes=30), "X", 1000, 600000)])
    assert not rules_of(a, "R15")
