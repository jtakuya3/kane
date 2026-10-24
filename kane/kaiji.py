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
    kind: str  # "自己株取得" / "大手との提携"
    buy: bool
    code: str  # 買い判断の対象（開示した会社）
    summary: str
    detail: dict = field(default_factory=dict)


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


def judge(code: str, title: str, body: str, big: BigCaps, cap_yen: float | None,
          buyback_min_pct: float = 5.0, small_max_oku: float = 300, issued_shares: float | None = None,
          price: float | None = None, yutai_min_yield_pct: float = 4.0) -> list[Verdict]:
    out = []
    for v in (judge_buyback(code, title, body, buyback_min_pct, issued_shares, cap_yen),
              judge_partner(code, title, body, big, cap_yen, small_max_oku),
              judge_yutai(code, title, body, price, yutai_min_yield_pct)):
        if v:
            out.append(v)
    return out
