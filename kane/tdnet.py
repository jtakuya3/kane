"""TDnet（適時開示情報閲覧サービス）の一覧を1秒おきに見て、新しい開示を拾う。

一覧ページ: https://www.release.tdnet.info/inbs/I_list_001_YYYYMMDD.html（100件ごとにページが分かれる）
PDF:        一覧の表題リンク（inbs/ からの相対パス）

    python -m kane.tdnet --check   # 今日の一覧の先頭と末尾、最新PDFの本文の先頭、判定結果を表示（PC側の動作確認）

ここは I/O だけ。判定は kaiji.py。
"""
from __future__ import annotations

import argparse
import html
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .kaiji import tdnet_code

log = logging.getLogger("kane")

BASE = "https://www.release.tdnet.info/inbs/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kane/0.1"


@dataclass(frozen=True)
class Disclosure:
    time: str  # "09:30"
    code: str  # 4桁（4498 / 338A）
    name: str
    title: str
    pdf: str  # 絶対URL


def list_url(day: date, page: int = 1) -> str:
    return f"{BASE}I_list_{page:03d}_{day:%Y%m%d}.html"


_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
# 実物は <td class="oddnew-L kjTime" noWrap>14:00</td> のように class が複数（偶奇の色＋kjXxx）
_CELL = re.compile(r"<td[^>]*class=\"[^\"]*\b(kj\w+)\b[^\"]*\"[^>]*>(.*?)</td>", re.S | re.I)
_HREF = re.compile(r"href=\"([^\"]+\.pdf)\"", re.I)
_TAG = re.compile(r"<[^>]+>")
_PAGER = re.compile(r"I_list_(\d{3})_\d{8}\.html")


def _text(s: str) -> str:
    return html.unescape(_TAG.sub("", s)).strip()


def parse_list(page_html: str) -> list[Disclosure]:
    """一覧ページの行を Disclosure にする（ページ内の順番のまま）。"""
    out = []
    for m in _ROW.finditer(page_html):
        cells = {k.lower(): v for k, v in _CELL.findall(m.group(1))}
        if "kjtime" not in cells or "kjtitle" not in cells:
            continue
        href = _HREF.search(cells["kjtitle"])
        if not href:
            continue
        pdf = href.group(1)
        if not pdf.lower().startswith("http"):
            pdf = BASE + pdf.lstrip("./")
        out.append(Disclosure(_text(cells["kjtime"]), tdnet_code(_text(cells.get("kjcode", ""))),
                              _text(cells.get("kjname", "")), _text(cells["kjtitle"]), pdf))
    return out


def page_count(page_html: str) -> int:
    nums = [int(x) for x in _PAGER.findall(page_html)]
    return max(nums) if nums else 1


def fetch(url: str, timeout: float = 4.0, etag: str | None = None) -> tuple[int, bytes, str | None]:
    """(status, body, etag)。304 のときは body が空。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"If-None-Match": etag} if etag else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        return e.code, b"", None


def decode(body: bytes) -> str:
    for enc in ("utf-8", "cp932"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def pdf_text(data: bytes, max_pages: int = 6) -> str:
    """PDF の先頭数ページの文字。pypdf が無い／画像だけなら空文字。"""
    try:
        from io import BytesIO

        from pypdf import PdfReader
    except ImportError:
        log.warning("pypdf が入っていません（pip install pypdf）。開示PDFの本文は読めません")
        return ""
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except Exception as e:
        log.warning("PDF を読めません: %s", e)
        return ""


class TdnetWatcher:
    """今日の一覧を見張り、まだ見ていない開示を返す。見た分は kane_data/tdnet_seen_YYYYMMDD.txt に残す。"""

    def __init__(self, data_dir: Path, newest_first: bool = True, poll_sec: float = 1.0):
        self.data_dir = data_dir
        self.newest_first = newest_first
        self.poll_sec = poll_sec
        self.day: date | None = None
        self.seen: set[str] = set()
        self.etag: str | None = None
        self.backoff = 0.0
        self.primed = False  # 起動時にその日の既出分を「見た」ことにしたか

    def _seen_path(self, day: date) -> Path:
        return self.data_dir / f"tdnet_seen_{day:%Y%m%d}.txt"

    def _roll(self, day: date):
        if self.day == day:
            return
        self.day, self.etag, self.primed = day, None, False
        self.seen = set()
        p = self._seen_path(day)
        if p.exists():
            self.seen = set(p.read_text(encoding="utf-8").split())
            self.primed = True  # 今日すでに動いていた → 既出分は記録済み

    def _remember(self, items: list[Disclosure]):
        if not items:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._seen_path(self.day), "a", encoding="utf-8") as f:
            for d in items:
                f.write(d.pdf + "\n")
        self.seen.update(d.pdf for d in items)

    def poll(self, now: datetime | None = None) -> list[Disclosure]:
        """新しい開示（まだ見ていないもの）。初回は既出分を全部「見た」ことにして空を返す。"""
        now = now or datetime.now()
        self._roll(now.date())
        if self.backoff > time.monotonic():
            return []
        status, body, etag = fetch(list_url(self.day, 1), etag=self.etag)
        if status == 304:
            return []
        if status == 404:
            self.primed = True  # 今日まだ1件も無い＝これから出るものは全部新しい
            return []
        if status in (403, 429) or status >= 500:
            self.backoff = time.monotonic() + 10
            log.warning("TDnet 一覧 HTTP %s（10秒休む）", status)
            return []
        self.etag = etag
        page = decode(body)
        items = parse_list(page)
        if not self.newest_first:
            n = page_count(page)
            if n > 1:
                st2, body2, _ = fetch(list_url(self.day, n))
                if st2 == 200:
                    items = parse_list(decode(body2))
        new = [d for d in items if d.pdf not in self.seen]
        if not self.primed:
            self.primed = True
            self._remember(new)  # 起動前の分は通知しない
            return []
        self._remember(new)
        return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="今日の一覧と最新PDFを読んで判定を表示")
    ap.add_argument("--date", help="YYYYMMDD（既定は今日）")
    ap.add_argument("--n", type=int, default=5, help="判定を試す件数")
    args = ap.parse_args()
    day = datetime.strptime(args.date, "%Y%m%d").date() if args.date else date.today()
    t0 = time.monotonic()
    status, body, _ = fetch(list_url(day, 1))
    print(f"一覧 {list_url(day, 1)} → HTTP {status}（{time.monotonic() - t0:.2f}秒）")
    if status != 200:
        print("一覧が取れません。日付（営業日か）とネットワークを確認してください")
        return
    page = decode(body)
    items = parse_list(page)
    print(f"ページ数 {page_count(page)} / このページ {len(items)}件")
    dump = Path("kane_data") / f"tdnet_page_{day:%Y%m%d}.html"
    try:
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_text(page, encoding="utf-8")
        print(f"ページを保存: {dump.resolve()}")
    except OSError:
        pass
    if not items:
        print("行を読めませんでした。HTMLの形が想定と違います。最初の .pdf の前後 1500文字:")
        i = page.find(".pdf")
        print(page[max(0, i - 1200): i + 300] if i >= 0 else "（.pdf が見つかりません。開示がまだ無いか、一覧の形が違います）")
        return
    print(f"先頭: {items[0].time} {items[0].code} {items[0].name} {items[0].title}")
    print(f"末尾: {items[-1].time} {items[-1].code} {items[-1].name} {items[-1].title}")
    print("→ 先頭の時刻が新しければ newest_first = true（既定）、古ければ false にする")
    from .kaiji import BigCaps, judge

    big = BigCaps.load(Path(__file__).resolve().parent.parent / "bigcaps.txt")
    for d in items[: args.n]:
        t1 = time.monotonic()
        st, pdf, _ = fetch(d.pdf, timeout=8)
        txt = pdf_text(pdf) if st == 200 else ""
        dt = time.monotonic() - t1
        print(f"\n--- {d.time} {d.code} {d.name} 「{d.title}」 PDF HTTP {st} {len(pdf) / 1024:.0f}KB 本文{len(txt)}字（{dt:.2f}秒）")
        print("   ", re.sub(r"\s+", " ", txt[:300]))
        for v in judge(d.code, d.title, txt, big, None):
            print("    判定:", v.kind, "買い" if v.buy else "見送り", v.summary)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()
