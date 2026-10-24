"""適時開示（TDnet）の表題と本文から「買い判断」を出す純粋な判定ロジック。I/O はしない。

判定は2つ（R18）:
  自己株取得  … 自己株式の取得（新規決定）で、発行済株式総数に対する割合が 5% 以上 → 買い
  大手との提携 … 提携・買収・連携の開示で、相手が時価総額1兆円以上の大手、開示した側が300億円以下 → 小型の方を買い
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


def norm(text: str) -> str:
    """全角→半角、空白を全部消す（pypdf は日本語の間に空白を入れることがある）。"""
    t = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", "", t)


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


def judge_buyback(code: str, title: str, body: str, min_pct: float = 5.0) -> Verdict | None:
    t = norm(title)
    if not BUYBACK_TITLE.search(t) or BUYBACK_SKIP.search(t):
        return None
    b = norm(body)
    pct = _ratio(b)
    sh = SHARES_NEAR.search(b)
    am = AMOUNT_NEAR.search(b)
    amount = ""
    if am:
        n = float(am.group(1).replace(",", ""))
        unit = am.group(2)
        oku = n / 100 if unit == "百万円" else (n if unit == "億円" else n / 1e8)
        amount = f"、上限 {oku:,.0f}億円"
    shares = f"、上限 {int(sh.group(1).replace(',', '')):,}株" if sh else ""
    if pct is None:
        return Verdict("自己株取得", False, code,
                       f"自己株式取得（割合はPDF参照{shares}{amount}）", {"pct": None})
    buy = pct >= min_pct
    return Verdict("自己株取得", buy, code,
                   f"自己株式取得 発行済の {pct:.1f}%{shares}{amount}" + ("  → 買い" if buy else f"（{min_pct:.0f}%未満）"),
                   {"pct": pct})


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


def judge(code: str, title: str, body: str, big: BigCaps, cap_yen: float | None,
          buyback_min_pct: float = 5.0, small_max_oku: float = 300) -> list[Verdict]:
    out = []
    v = judge_buyback(code, title, body, buyback_min_pct)
    if v:
        out.append(v)
    v = judge_partner(code, title, body, big, cap_yen, small_max_oku)
    if v:
        out.append(v)
    return out
