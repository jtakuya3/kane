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
    assert v and not v.buy and "確認中" in v.summary  # 後追いで推定する


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


def test_tob_by_giant_counts_as_partner():
    v = judge_partner("4047", "トヨタ自動車株式会社による当社株式に対する公開買付けに関する賛同の意見表明のお知らせ", "", BIG, 150e8)
    assert v and v.buy and v.detail["partner"] == "トヨタ自動車"


def test_buyback_ratio_fallback_without_word_wariai():
    body = "取得し得る株式の総数 500,000株（発行済株式総数の 6.1%）取得価額の総額 300百万円"
    v = judge_buyback("4498", "自己株式取得に係る事項の決定に関するお知らせ", body)
    assert v and v.buy and v.detail["pct"] == 6.1


def test_watcher_404_then_first_disclosure_is_reported(tmp_path, monkeypatch):
    import kane.tdnet as td
    st = {"code": 404}
    monkeypatch.setattr(td, "fetch", lambda url, timeout=4.0, etag=None: (st["code"], LIST_HTML.encode("utf-8") if st["code"] == 200 else b"", None))
    w = TdnetWatcher(tmp_path)
    now = datetime(2026, 10, 24, 8, 30)
    assert w.poll(now) == []
    st["code"] = 200
    assert [d.code for d in w.poll(now)] == ["4498", "338A"]  # その日の最初の開示を飲み込まない


def test_buyback_estimates_ratio_when_pdf_has_none():
    body = "取得し得る株式の総数 1,000,000株（上限） 取得価額の総額 2,000百万円（上限）"
    v = judge_buyback("4498", "自己株式取得に係る事項の決定に関するお知らせ", body)
    assert v and v.detail["pct"] is None and "確認中" in v.summary
    v = judge_buyback("4498", "自己株式取得に係る事項の決定に関するお知らせ", body, issued_shares=16_729_200)
    assert v and v.buy and abs(v.detail["pct"] - 5.98) < 0.01 and "上限株数÷発行済" in v.summary
    v = judge_buyback("4498", "自己株式取得に係る事項の決定に関するお知らせ", body, cap_yen=600e8)
    assert v and not v.buy and abs(v.detail["pct"] - 3.33) < 0.01 and "上限金額÷時価総額" in v.summary
    body2 = body + " 発行済株式総数（自己株式を除く） 12,500,000株"
    v = judge_buyback("4498", "自己株式取得に係る事項の決定に関するお知らせ", body2, cap_yen=600e8)
    assert v and v.buy and v.detail["pct"] == 8.0  # 本文の発行済株式数が最優先


def test_yutai_yield():
    from kane.kaiji import judge_yutai
    body = "２．優待内容 100株以上 保有の株主様に QUOカード 3,000円分 を贈呈 500株以上 5,000円分"
    v = judge_yutai("4498", "株主優待制度の新設に関するお知らせ", body, price=600)
    assert v and v.buy and abs(v.detail["yield"] - 5.0) < 0.01 and "3,000円相当" in v.summary
    v = judge_yutai("4498", "株主優待制度の拡充に関するお知らせ", body, price=1500)
    assert v and not v.buy and abs(v.detail["yield"] - 2.0) < 0.01
    v = judge_yutai("4498", "株主優待制度の新設に関するお知らせ", body, price=None)
    assert v and not v.buy and "株価不明" in v.summary
    assert judge_yutai("4498", "株主優待制度の廃止に関するお知らせ", body, 600) is None
    assert judge_yutai("4498", "株主優待制度に関するお知らせ", body, 600) is None  # 新設・拡充の言葉が無い


def test_feed_inserts_links_as_tagged_segments():
    from kane.feed import _insert_with_links

    class FakeText:
        def __init__(self):
            self.buf = ""
            self.tags = []

        def insert(self, at, s, tags):
            line, col = map(int, at.split("."))
            self.buf = self.buf[:col] + s + self.buf[col:]
            self.tags.append((s, tags))

        def index(self, expr):
            base, plus = expr.split("+")
            n = int(plus.rstrip("c"))
            return f"1.{int(base.split('.')[1]) + n}"

    t = FakeText()
    body = "開示 https://www.release.tdnet.info/inbs/a.pdf\n（検知まで 1.2秒）\n"
    _insert_with_links(t, body, "important")
    assert t.buf == body
    assert ("https://www.release.tdnet.info/inbs/a.pdf", ("important", "link")) in t.tags
