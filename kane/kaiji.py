"""適時開示（TDnet）の表題と本文から「買い判断」を出す純粋な判定ロジック。I/O はしない。

判定は3つ（R18）:
  自己株取得  … 自己株式の取得（新規決定）で、発行済株式総数に対する割合が 5% 以上 → 買い
                PDF に割合が無ければ 上限株数÷発行済株式数（または 上限金額÷時価総額）で推定する
  大手との提携 … 提携・買収・連携の開示で、相手が時価総額1兆円以上の大手、開示した側が300億円以下 → 小型の方を買い
  株主優待    … 優待の新設・拡充で、100株あたりの優待額÷（株価×100株）が 4% 以上 → 買い
時価総額はざっくり（楽天RSS「時価総額」）。分からなければ「不明」と添えて出す（黙らない）。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# 表題のふるい
BUYBACK_TITLE = re.compile(r"自己株式.{0,12}?(取得|買付|公開買付)")
BUYBACK_SKIP = re.compile(r"取得状況|取得結果|取得の終了|取得終了|買付けの結果|買付け結果|消却|処分|譲渡|立会外分売|満了|変更に関する")
PARTNER_TITLE = re.compile(r"資本業務提携|業務提携|資本提携|包括提携|戦略的提携|買収|株式取得|株式の取得|子会社化|"
                           r"連携|協業|共同開発|共同事業|パートナーシップ|アライアンス|出資|公開買付|意見表明")  # 大手によるTOBも
PARTNER_SKIP = re.compile(r"解消|終了|中止|延期|訂正|進捗|状況")
# 「AWSを利用」のような“インフラを使うだけ”の表現（提携ではない）
USE_ONLY = re.compile(r"(を|の)(利用|採用|活用|導入|使用|上で)")

RATIO_NEAR = re.compile(r"割合[^0-9０-９%％]{0,40}?([0-9]+(?:\.[0-9]+)?)\s*[%％]")
RATIO_FALLBACK = re.compile(r"発行済株式総数[^0-9%％]{0,30}?([0-9]+(?:\.[0-9]+)?)\s*[%％]")  # 「発行済株式総数の7.2%」
ANY_PCT = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*[%％]")
SHARES_NEAR = re.compile(r"取得し得る株式の総数[^0-9]{0,30}?([0-9,]+)\s*株")
AMOUNT_NEAR = re.compile(r"取得価額の総額[^0-9]{0,30}?([0-9,]+)\s*(百万円|億円|円)")
ISSUED_NEAR = re.compile(r"発行済株式総数[^0-9%％]{0,20}?([0-9,]{7,})\s*株")  # 本文に書いてある発行済株式数


YUTAI_TITLE = re.compile(r"株主優待")
YUTAI_GOOD = re.compile(r"新設|導入|拡充|拡大|増額|開始|変更")
YUTAI_SKIP = re.compile(r"廃止|縮小|中止|終了|一時停止")
YUTAI_AMOUNT = re.compile(r"([0-9,]{3,7})\s*円\s*(分|相当|の|分の)")  # 「QUOカード 1,000円分」「3,000円相当」

# 決算短信：別紙の「修正のお知らせ」を出さずに、短信の中だけで業績予想・配当予想を修正する会社がある
TANSHIN_TITLE = re.compile(r"決算短信")
TANSHIN_SKIP = re.compile(r"訂正|補足|説明資料|英訳|English")
REV_FLAG = re.compile(r"業績予想[^有無]{0,20}?修正の有無[^有無]{0,6}(有|無)")
DIV_FLAG = re.compile(r"配当予想[^有無]{0,20}?修正の有無[^有無]{0,6}(有|無)")
# 通期の予想行：「通期 12,000 5.2 1,500 20.3 1,480 19.0 1,000 15.0 80.00」→ 売上高 % 営業利益 % …
FULL_ROW = re.compile(r"通期\s+([△▲\-－]?[0-9,]+)\s+([△▲\-－]?[0-9]+(?:\.[0-9]+)?)\s+([△▲\-－]?[0-9,]+)\s+([△▲\-－]?[0-9]+(?:\.[0-9]+)?)")

# 公開買付け（TOB）：買われる側（対象者）の株は TOB 価格まで跳ぶ
TOB_TITLE = re.compile(r"公開買付け?の(開始|実施)|公開買付け?に関する(お知らせ|意見表明|賛同)|株式等に対する公開買付")
TOB_SKIP = re.compile(r"結果|終了|変更|訂正|延長|撤回|自己株式")
TOB_TARGET_CODE = re.compile(r"(?:証券コード|コード)[：:]?\s*([0-9]{4}|[0-9]{3}[A-Z])")
TOB_PRICE = re.compile(r"買付け?(?:等の)?価格.{0,60}?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,8})円")  # 「買付け等の価格 1株につき 1,500円」
TOB_BY = re.compile(r"(.{2,30}?)(?:株式会社|\(株\)|（株）)?による当社")  # 意見表明：「○○による当社株式に対する…」


def norm(text: str) -> str:
    """全角→半角、空白を全部消す（pypdf は日本語の間に空白を入れることがある）。"""
    t = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", "", t)


def norm_sp(text: str) -> str:
    """全角→半角、空白は1つに畳む（表の数字を区切るために残す）。"""
    t = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", t)


def _signed(x: str) -> float:
    x = x.replace(" ", "")
    neg = x[:1] in "△▲-－‐"
    v = float(x.lstrip("△▲-－‐"))
    return -v if neg else v


def tdnet_code(code5: str) -> str:
    """TDnet の5桁コード（44980 / 338A0）→ 4桁（4498 / 338A）。"""
    c = str(code5).strip()
    return c[:-1] if len(c) == 5 and c[-1] == "0" else c


@dataclass
class Verdict:
    kind: str  # "自己株取得" / "大手との提携" / "TOB" / "株主優待" / "決算短信"
    buy: bool
    code: str  # 買い判断の対象（開示した会社）
    summary: str
    detail: dict = field(default_factory=dict)
    level: str | None = None  # 通知の区分を上書きしたいとき（"要確認" など）。無ければ 買い／参考


@dataclass
class BigCaps:
    """時価総額1兆円以上の相手の名前。手書きの別名表＋朝に universe の時価総額から足したもの。"""
    names: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path, caps: dict[str, float] | None = None, universe_names: dict[str, str] | None = None,
             big_min_oku: float = 10_000) -> "BigCaps":
        names: list[str] = []
        try:
            for line in open(path, encoding="utf-8"):
                line = line.split("#", 1)[0].strip()
                if line:
                    names.append(norm(line))
        except OSError:
            pass
        if caps and universe_names:
            for code, cap in caps.items():
                if cap is not None and cap >= big_min_oku * 1e8:
                    n = norm(universe_names.get(code, ""))
                    if len(n) >= 4 and n not in names:
                        names.append(n)
        return cls(sorted(set(names), key=len, reverse=True))

    def find(self, text: str) -> str | None:
        for n in self.names:
            if n and n in text:
                return n
        return None


def _ratio(body: str) -> float | None:
    m = RATIO_NEAR.search(body) or RATIO_FALLBACK.search(body)
    return float(m.group(1)) if m else None


def judge_buyback(code: str, title: str, body: str, min_pct: float = 5.0,
                  issued_shares: float | None = None, cap_yen: float | None = None) -> Verdict | None:
    """自己株式取得。割合が本文に無ければ、上限株数÷発行済株式数（本文→CSV→時価総額÷株価の順）、
    それも無ければ 上限金額÷時価総額 で推定する。推定できなければ「確認中」で出す（後追いで埋める）。"""
    t = norm(title)
    if not BUYBACK_TITLE.search(t) or BUYBACK_SKIP.search(t):
        return None
    b = norm(body)
    pct = _ratio(b)
    sh = SHARES_NEAR.search(b)
    am = AMOUNT_NEAR.search(b)
    amount_yen = None
    amount = ""
    if am:
        n = float(am.group(1).replace(",", ""))
        unit = am.group(2)
        amount_yen = n * 1e6 if unit == "百万円" else (n * 1e8 if unit == "億円" else n)
        amount = f"、上限 {amount_yen / 1e8:,.0f}億円"
    shares_n = int(sh.group(1).replace(",", "")) if sh else None
    shares = f"、上限 {shares_n:,}株" if shares_n else ""
    how = ""
    if pct is None:
        iss = ISSUED_NEAR.search(b)
        issued = float(iss.group(1).replace(",", "")) if iss else issued_shares
        if shares_n and issued:
            pct, how = shares_n / issued * 100, "（推定：上限株数÷発行済）"
        elif amount_yen and cap_yen:
            pct, how = amount_yen / cap_yen * 100, "（推定：上限金額÷時価総額）"
    if pct is None:
        return Verdict("自己株取得", False, code,
                       f"自己株式取得 割合 確認中{shares}{amount}", {"pct": None, "shares": shares_n, "amount_yen": amount_yen})
    buy = pct >= min_pct
    return Verdict("自己株取得", buy, code,
                   f"自己株式取得 発行済の {pct:.1f}%{how}{shares}{amount}" + ("  → 買い" if buy else f"（{min_pct:.0f}%未満）"),
                   {"pct": pct, "shares": shares_n, "amount_yen": amount_yen, "estimated": bool(how)})


def judge_partner(code: str, title: str, body: str, big: BigCaps, cap_yen: float | None,
                  small_max_oku: float = 300, head_chars: int = 600) -> Verdict | None:
    t = norm(title)
    if not PARTNER_TITLE.search(t) or PARTNER_SKIP.search(t):
        return None
    head = t + norm(body)[:head_chars]
    partner = big.find(head)
    if not partner:
        return None
    # 相手の名前の直後が「を利用／採用」なら、インフラを使うだけで提携ではない
    uses = 0
    for m in re.finditer(re.escape(partner), head):
        after = re.sub(r"^[)）」』\]]+", "", head[m.end(): m.end() + 14])  # 「（AWS）を利用」の閉じ括弧を飛ばす
        if USE_ONLY.match(after):
            uses += 1
        else:
            break
    else:
        if uses:
            return None  # 出てくる場所が全部「利用・採用」なら提携ではない
    if cap_yen is None:
        cap_txt, small = "時価総額 不明", True
    else:
        small = cap_yen <= small_max_oku * 1e8
        cap_txt = f"時価総額 {cap_yen / 1e8:,.0f}億円"
    buy = small
    return Verdict("大手との提携", buy, code,
                   f"{partner} との提携・買収（{cap_txt}）" + ("  → 小型の方を買い" if buy else f"（{small_max_oku:.0f}億円超）"),
                   {"partner": partner, "cap_yen": cap_yen})


def judge_yutai(code: str, title: str, body: str, price: float | None, min_yield_pct: float = 4.0,
                unit_shares: int = 100) -> Verdict | None:
    """株主優待の新設・拡充。100株あたりの優待額 ÷（株価×100株）＝優待利回り。"""
    t = norm(title)
    if not YUTAI_TITLE.search(t) or YUTAI_SKIP.search(t) or not YUTAI_GOOD.search(t):
        return None
    b = norm(body)
    i = b.find(f"{unit_shares}株")
    seg = b[i: i + 400] if i >= 0 else b
    m = YUTAI_AMOUNT.search(seg) or YUTAI_AMOUNT.search(b)
    if not m:
        return Verdict("株主優待", False, code, "株主優待 新設・拡充（優待額はPDF参照）", {"yield": None})
    amt = float(m.group(1).replace(",", ""))
    if not price:
        return Verdict("株主優待", False, code, f"株主優待 新設・拡充 {unit_shares}株で {amt:,.0f}円相当（株価不明で利回り未算出）",
                       {"yield": None, "amount": amt})
    y = amt / (price * unit_shares) * 100
    buy = y >= min_yield_pct
    return Verdict("株主優待", buy, code,
                   f"株主優待 新設・拡充 {unit_shares}株で {amt:,.0f}円相当 ＝ 優待利回り {y:.1f}%（株価 {price:,.0f}円）"
                   + ("  → 買い" if buy else f"（{min_yield_pct:.0f}%未満）"),
                   {"yield": y, "amount": amt})


def judge_tanshin(code: str, title: str, body: str) -> Verdict | None:
    """決算短信。1ページ目の「業績予想の修正の有無：有」「配当予想の修正の有無：有」を見る。
    有なら「要確認」として赤で出す（前回予想が短信に載っていないので上方・下方は本文で確認）。
    通期予想の営業利益と前年比が読めれば添える。無・無なら何も出さない（決算期は1日に数百件ある）。"""
    t = norm(title)
    if not TANSHIN_TITLE.search(t) or TANSHIN_SKIP.search(t):
        return None
    b = norm_sp(body)
    head = re.sub(r"\s+", "", b[:4000])
    rev = REV_FLAG.search(head)
    div = DIV_FLAG.search(head)
    rev_on = bool(rev and rev.group(1) == "有")
    div_on = bool(div and div.group(1) == "有")
    if not rev_on and not div_on:
        return None
    m = FULL_ROW.search(b)
    op = ""
    if m:
        try:
            sales, sales_pct, opv, op_pct = (_signed(m.group(1).replace(",", "")), _signed(m.group(2)),
                                             _signed(m.group(3).replace(",", "")), _signed(m.group(4)))
            op = f"  通期予想 売上高 {sales:,.0f}百万円（前年比 {sales_pct:+.1f}%）営業利益 {opv:,.0f}百万円（{op_pct:+.1f}%）"
        except ValueError:
            op = ""
    what = "・".join(x for x, on in (("業績予想", rev_on), ("配当予想", div_on)) if on)
    return Verdict("決算短信", False, code, f"決算短信の中で {what} を修正（有）{op}  上方か下方かはPDFで確認",
                   {"revised": rev_on, "dividend_revised": div_on}, level="要確認")


def judge_tob(code: str, title: str, body: str, price_of=None) -> Verdict | None:
    """公開買付け（TOB）。買う側の開示なら表題・本文の「証券コード：7477」から対象者を拾い、対象者を買い。
    対象者自身の意見表明（賛同）なら、その対象者＝開示した会社を買い。買付価格と現在値からプレミアムを出す。"""
    t = norm(title)
    if not TOB_TITLE.search(t) or TOB_SKIP.search(t):
        return None
    b = norm(body)
    m = TOB_TARGET_CODE.search(t) or TOB_TARGET_CODE.search(b[:1500])
    target = m.group(1) if m else None
    by = TOB_BY.search(t)
    if "当社株式" in t or "当社株券" in t or by:
        target = code  # 対象者（買われる側）自身の開示
    if not target or target == code and not ("当社株式" in t or "当社株券" in t or by):
        return None
    pm = TOB_PRICE.search(b)
    tob_price = float(pm.group(1).replace(",", "")) if pm else None
    cur = price_of(target) if price_of else None
    prem = f"、プレミアム {(tob_price / cur - 1):+.0%}（現在値 {cur:,.0f}円）" if tob_price and cur else ""
    if tob_price and cur and tob_price <= cur:
        return Verdict("TOB", False, target, f"公開買付け 買付価格 {tob_price:,.0f}円 は現在値以下（ディスカウントTOB）", 
                       {"tob_price": tob_price, "target": target})
    who = f"{by.group(1)} による" if by else (f"{code} による" if target != code else "")
    px = f"買付価格 {tob_price:,.0f}円" if tob_price else "買付価格はPDF参照"
    return Verdict("TOB", True, target,
                   f"{who}公開買付け（対象 {target}）{px}{prem}  → 対象者を買い",
                   {"tob_price": tob_price, "target": target, "acquirer": code if target != code else None})


def judge(code: str, title: str, body: str, big: BigCaps, cap_yen: float | None,
          buyback_min_pct: float = 5.0, small_max_oku: float = 300, issued_shares: float | None = None,
          price: float | None = None, yutai_min_yield_pct: float = 4.0, price_of=None) -> list[Verdict]:
    out = []
    tob = judge_tob(code, title, body, price_of)
    for v in (judge_buyback(code, title, body, buyback_min_pct, issued_shares, cap_yen),
              None if tob else judge_partner(code, title, body, big, cap_yen, small_max_oku),  # TOB は提携より優先
              judge_yutai(code, title, body, price, yutai_min_yield_pct),
              judge_tanshin(code, title, body),
              tob):
        if v:
            out.append(v)
    return out
