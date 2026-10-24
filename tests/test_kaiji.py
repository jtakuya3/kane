"""R18 適時開示の判定（kaiji）と TDnet 一覧の読み取り（tdnet）。ネットは使わない。"""
from datetime import datetime

from kane.kaiji import BigCaps, judge, judge_buyback, judge_partner, norm, tdnet_code
from kane.tdnet import TdnetWatcher, page_count, parse_list

LIST_HTML = """
<table><tr><th>時刻</th></tr>
<tr><td class="kjTime">09:30</td><td class="kjCode">44980</td><td class="kjName">サイバートラスト</td>
<td class="kjTitle"><a href="081220261024512345.pdf" target="_blank">業績予想の修正に関するお知らせ</a></td>
<td class="kjXbrl"></td><td class="kjPlace">東</td><td class="kjHistroy"></td></tr>
<tr><td class="kjTime">09:00</td><td class="kjCode">338A0</td><td class="kjName">ゼンムテック</td>
<td class="kjTitle"><a href="./081220261024512300.pdf">自己株式の取得に係る事項の決定に関するお知らせ</a></td>
<td class="kjXbrl"></td><td class="kjPlace">東</td><td class="kjHistroy"></td></tr>
</table>
<div class="pager"><a href="I_list_001_20261024.html">1</a> <a href="I_list_002_20261024.html">2</a> <a href="I_list_003_20261024.html">3</a></div>
"""


def test_tdnet_code_strips_trailing_zero():
    assert tdnet_code("44980") == "4498" and tdnet_code("338A0") == "338A" and tdnet_code("4498") == "4498"


def test_parse_list_and_pages():
    items = parse_list(LIST_HTML)
    assert [d.code for d in items] == ["4498", "338A"]
    assert items[0].time == "09:30" and items[0].title == "業績予想の修正に関するお知らせ"
    assert items[0].pdf == "https://www.release.tdnet.info/inbs/081220261024512345.pdf"
    assert items[1].pdf.endswith("/081220261024512300.pdf")
    assert page_count(LIST_HTML) == 3 and page_count("<html></html>") == 1


def test_watcher_primes_on_first_poll_and_persists(tmp_path, monkeypatch):
    import kane.tdnet as td
    pages = [LIST_HTML]
    monkeypatch.setattr(td, "fetch", lambda url, timeout=4.0, etag=None: (200, pages[-1].encode("utf-8"), None))
    w = TdnetWatcher(tmp_path)
    now = datetime(2026, 10, 24, 9, 31)
    assert w.poll(now) == []  # 起動時の既出分は通知しない
    pages.append(LIST_HTML.replace('<tr><td class="kjTime">09:30</td>',
                                   '<tr><td class="kjTime">09:35</td><td class="kjCode">40470</td><td class="kjName">関東電化</td>'
                                   '<td class="kjTitle"><a href="new.pdf">資本業務提携のお知らせ</a></td></tr>'
                                   '<tr><td class="kjTime">09:30</td>'))
    new = w.poll(now)
    assert [d.code for d in new] == ["4047"]
    assert w.poll(now) == []  # 同じものは二度と出ない
    w2 = TdnetWatcher(tmp_path)  # 再起動しても見た分は記憶している
    assert w2.poll(now) == []
    assert "new.pdf" in (tmp_path / "tdnet_seen_20261024.txt").read_text()


BUYBACK_BODY = """
１．自己株式の取得を行う理由  株主還元の充実
２．取得に係る事項の内容
（１）取得対象株式の種類  当社普通株式
（２）取得し得る株式の総数  1,200,000 株（上限）
（発行済株式総数（自己株式を除く）に対する割合 ７．２％）
（３）株式の取得価額の総額  1,500 百万円（上限）
（４）取得期間  2026年10月27日～2027年3月31日
"""


def test_buyback_ratio_from_spaced_fullwidth_text():
    v = judge_buyback("4498", "自己株式の取得に係る事項の決定に関するお知らせ", BUYBACK_BODY)
    assert v and v.buy and v.detail["pct"] == 7.2
    assert "7.2%" in v.summary and "1,200,000株" in v.summary and "15億円" in v.summary


def test_buyback_below_threshold_and_skips():
    small = BUYBACK_BODY.replace("７．２％", "２．０％")
    v = judge_buyback("4498", "自己株式取得に係る事項の決定に関するお知らせ", small)
    assert v and not v.buy
    assert judge_buyback("4498", "自己株式の取得状況に関するお知らせ", BUYBACK_BODY) is None
    assert judge_buyback("4498", "自己株式の消却に関するお知らせ", BUYBACK_BODY) is None
    assert judge_buyback("4498", "業績予想の修正に関するお知らせ", BUYBACK_BODY) is None
    v = judge_buyback("4498", "自己株式の取得に係る事項の決定に関するお知らせ", "")  # 画像PDF
    assert v and not v.buy and "PDF参照" in v.summary


BIG = BigCaps(["トヨタ自動車", "トヨタ", "AWS", "Microsoft", "マイクロソフト"])


def test_partner_small_with_giant_is_buy():
    body = "当社は、トヨタ自動車株式会社（以下「トヨタ」）との間で資本業務提携契約を締結することを決議しました。"
    v = judge_partner("4047", "トヨタ自動車株式会社との資本業務提携に関するお知らせ", body, BIG, 120e8)
    assert v and v.buy and v.detail["partner"] == "トヨタ自動車" and "120億円" in v.summary
    v2 = judge_partner("4047", "資本業務提携に関するお知らせ", body, BIG, None)
    assert v2 and v2.buy and "不明" in v2.summary  # 時価総額が分からなくても出す
    v3 = judge_partner("4047", "資本業務提携に関するお知らせ", body, BIG, 900e8)
    assert v3 and not v3.buy  # 300億円超は買わない


def test_partner_negatives():
    assert judge_partner("4047", "資本業務提携の解消に関するお知らせ", "トヨタ", BIG, 100e8) is None
    assert judge_partner("4047", "業務提携に関するお知らせ", "株式会社ABCとの業務提携", BIG, 100e8) is None  # 相手が大手でない
    body = "新サービスの基盤として Amazon Web Services（AWS）を利用します。"
    assert judge_partner("4047", "新サービス開始と業務提携に関するお知らせ", body, BIG, 100e8) is None  # 使うだけ


def test_bigcaps_load_adds_universe_giants(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("Microsoft  # 海外\n\nトヨタ\n", encoding="utf-8")
    caps = {"7203": 40e12, "4498": 300e8, "6758": 15e12}
    names = {"7203": "トヨタ自動車", "4498": "サイバートラスト", "6758": "ソニーグループ"}
    big = BigCaps.load(f, caps, names, 10_000)
    assert set(big.names) == {"Microsoft", "トヨタ", "トヨタ自動車", "ソニーグループ"}
    assert big.names[0] in ("トヨタ自動車", "ソニーグループ", "Microsoft")  # 長いものから当てる


def test_judge_runs_both_rules():
    vs = judge("4498", "自己株式の取得に係る事項の決定に関するお知らせ", BUYBACK_BODY, BIG, 100e8)
    assert [v.kind for v in vs] == ["自己株取得"]


def test_norm_removes_spaces_and_fullwidth():
    assert norm("７．２ ％  発行済") == "7.2%発行済"
