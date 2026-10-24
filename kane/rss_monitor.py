"""楽天RSS版のライブ監視：Excelのセルを定期的に読み → ルール判定 → Slack通知＋CSV保存。

config.toml の [source] type = "rss" のとき kane.monitor から呼ばれる。
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from .config import Config, apply_baseline
from .engine import Engine
from .rss import SCAN_SHEET, WATCH_SHEET, ExcelRss, RssError, load_universe, row_to_snapshot, scan_fields, watch_fields
from .sinks import Notifier, Recorder

log = logging.getLogger("kane")


def _hm(s: str):
    h, m = s.split(":")
    return datetime.now().replace(hour=int(h), minute=int(m), second=0, microsecond=0).time()


class RssMonitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        r = cfg.rss
        wb = Path(r.workbook)
        self.rss = ExcelRss(r, wb if wb.is_absolute() else cfg.base_dir / wb)
        self.notifier = Notifier(cfg.slack_webhook_file, cfg.slack_enabled, cfg.beep, cfg.feed, cfg.dialog, cfg.quiet_after,
                                  cfg.quiet_except)
        self.recorder = Recorder(cfg.data_dir, cfg.record_snapshots)
        self.muted = {s.code for s in cfg.symbols if s.mute}
        self.watch = [s for s in cfg.symbols if not s.mute]
        self.pinned = {s.code for s in self.watch}
        self.scan = load_universe(cfg.base_dir / r.universe_csv, self.pinned | self.muted, r.max_scan)
        for s_ in self.scan:
            apply_baseline(s_, cfg.baseline)
        self.wf, self.sf = watch_fields(r), scan_fields(r)
        self.engine = Engine(self.watch + self.scan, cfg.rules, on_bar=self.recorder.bar)
        self.infos = {s.code: s for s in self.watch + self.scan}
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.last: dict[str, tuple] = {}
        self.ytd_done: set[str] = set()
        self.count = 0
        self.stat = {"t": time.monotonic(), "n": 0, "sec": 0.0, "changed": 0, "max": 0.0}
        self.wstat = {"t": time.monotonic(), "n": 0, "sec": 0.0, "changed": 0, "max": 0.0}
        self.lock = threading.Lock()  # engine・recorder・emit を2スレッドから使うため
        self.watch_running = False
        self.caps: dict[str, float] = {}  # 銘柄 → 時価総額（円）。スキャンの読み取りで更新、R18 で使う
        self.names = {s.code: s.name for s in self.watch + self.scan}

    # ---- 準備 ----
    def setup_sheets(self):
        self.rss.connect()
        self.rss.setup(WATCH_SHEET, [s.code for s in self.watch], self.wf)
        if self.scan:
            self.rss.setup(SCAN_SHEET, [s.code for s in self.scan], self.sf)
        log.info("RSSシート準備：固定%d銘柄（%d列） / スキャン%d銘柄（%d列）",
                 len(self.watch), len(self.wf), len(self.scan), len(self.sf))

    def check(self, wait_sec: float = 8):
        if self.notifier.feed:
            self.notifier.send("kane アラート窓のテスト表示（監視中はここに通知が流れます）", True, "R13")
        self.setup_sheets()
        print(f"RSSの式を書き込みました。{wait_sec:.0f}秒待って値を読みます…")
        time.sleep(wait_sec)
        rows = self.rss.read(WATCH_SHEET, len(self.watch), len(self.wf))
        for s, row in list(zip(self.watch, rows))[:3]:
            print(f"\n=== {s.code} {s.name} ===")
            for (key, item), v in zip(self.wf[:12], row[:12]):
                print(f"  {item:<14} → {v!r}")
        empty = [item for j, (_, item) in enumerate(self.wf)
                 if all(r[j] in (None, "") for r in rows)]
        if empty:
            print("\n全銘柄で空だった項目（項目名が違うか、この項目は提供されていない）:", empty)
        vw = [k for k, _ in self.wf]
        if "value" in vw and rows:
            r0 = rows[0]
            v, q = r0[vw.index("value")], r0[vw.index("volume")]
            if isinstance(v, (int, float)) and isinstance(q, (int, float)) and q:
                print(f"\nVWAP（売買代金×{self.cfg.rss.value_unit:g}÷出来高）: {self.watch[0].code} = {v * self.cfg.rss.value_unit / q:,.1f}")
        bad = sorted({item for row in rows for (k, item), v in zip(self.wf, row)
                      if isinstance(v, int) and v < -2_000_000_000})
        if bad:
            print("\nエラーになった項目（項目名が違う可能性。config.toml の [rss.items] で直せます）:", bad)
        if self.scan:
            t0 = time.monotonic()
            srows = self.rss.read(SCAN_SHEET, len(self.scan), len(self.sf))
            sec = time.monotonic() - t0
            got = sum(1 for r in srows if r and r[0] not in (None, ""))
            print(f"\nスキャン：{len(self.scan)}銘柄中 {got}銘柄で現在値を取得（読み取り {sec:.2f}秒）")
        print("Slack:", "送信する" if self.notifier.url else "送信しない（画面のアラート窓のみ）")

    # ---- 通知 ----
    def emit(self, alerts, snap_by_code):
        for a in alerts:
            if a.symbol not in self.pinned:
                s = snap_by_code.get(a.symbol)
                value = (s.volume * (s.vwap or s.price)) if s else 0
                if a.rule not in self.cfg.rss.scan_rules or value < self.cfg.rss.scan_min_value_yen:
                    continue
            self.count += 1
            self.recorder.alert(a)
            pop = a.rule in self.cfg.popup_rules or f"{a.rule}:{a.level}" in self.cfg.popup_rules
            self.pool.submit(self.notifier.send, a.message, pop, f"{a.rule}:{a.level}", a.ts)

    # ---- 1回分の読み取り ----
    def _process(self, infos, fields, rows, record: bool, now: datetime):
        """シートの行を Snapshot にして判定する（engine は lock の中で使う）。"""
        snaps, alerts = {}, []
        for info, row in zip(infos, rows):
            key = tuple(row)
            if self.last.get(info.code) == key:
                continue  # 変化なし
            self.last[info.code] = key
            snap, extra = row_to_snapshot(info.code, fields, row, now, self.cfg.rss.special_values,
                                          self.cfg.rss.value_unit)
            if extra.get("cap"):
                self.caps[info.code] = extra["cap"] * self.cfg.tdnet.cap_unit
            if info.code not in self.ytd_done and extra.get("ytd_high"):
                # 最初に読めた年初来高値（寄り前なら前日までの値）を基準にする
                if info.ytd_high is None:
                    info.ytd_high = extra["ytd_high"]
                self.ytd_done.add(info.code)
            if snap is None:
                continue
            snaps[info.code] = snap
            with self.lock:
                if record:
                    self.recorder.snapshot(snap)
                alerts += self.engine.process(snap)
        return snaps, alerts

    def poll(self):
        """スキャン銘柄（全銘柄）を1回読む。固定銘柄は poll_watch が別スレッドで読む。"""
        now = datetime.now()
        snaps, alerts = {}, []
        if self.scan:
            rows = self.rss.read(SCAN_SHEET, len(self.scan), len(self.sf))
            snaps, alerts = self._process(self.scan, self.sf, rows, False, now)
            self.stat["changed"] += len(snaps)
        if not self.watch_running and self.watch:  # 固定銘柄スレッドが動いていないときは自分で読む
            rows = self.rss.read(WATCH_SHEET, len(self.watch), len(self.wf))
            s2, a2 = self._process(self.watch, self.wf, rows, True, now)
            snaps.update(s2)
            alerts += a2
        with self.lock:
            alerts += self.engine.tick(now)
            self.emit(alerts, snaps)

    def poll_watch(self, rss: ExcelRss):
        """固定銘柄（板・成行）を1回読む。watch_poll_sec ごとに別スレッドで呼ぶ。"""
        now = datetime.now()
        rows = rss.read(WATCH_SHEET, len(self.watch), len(self.wf))
        snaps, alerts = self._process(self.watch, self.wf, rows, True, now)
        self.wstat["changed"] += len(snaps)
        if alerts:
            with self.lock:
                self.emit(alerts, snaps)

    def _watch_loop(self, stop: threading.Event):
        """固定銘柄専用の読み取りスレッド。Excel への接続は自分の分を持つ（COM はスレッドごと）。"""
        r = self.cfg.rss
        wb = Path(r.workbook)
        rss = ExcelRss(r, wb if wb.is_absolute() else self.cfg.base_dir / wb)
        try:
            rss.connect()
        except Exception as e:
            log.warning("固定銘柄スレッド：Excelに接続できません（メインの1秒周期で読みます）: %s", e)
            return
        self.watch_running = True
        log.info("固定銘柄 %d銘柄を %.1f秒ごとに別スレッドで読みます", len(self.watch), r.watch_poll_sec)
        try:
            while not stop.is_set():
                t0 = time.monotonic()
                try:
                    self.poll_watch(rss)
                except Exception as e:
                    log.warning("固定銘柄の読み取りエラー: %s（2秒後に再試行）", e)
                    time.sleep(2)
                    continue
                self._log_speed(time.monotonic() - t0, stat=self.wstat, label="固定")
                time.sleep(max(0.02, r.watch_poll_sec - (time.monotonic() - t0)))
        finally:
            self.watch_running = False

    def _log_speed(self, sec: float, every: float = 300, stat: dict | None = None, label: str = "スキャン"):
        """5分ごとに読み取り1回の時間と、値が動いた銘柄数を記録する（固定・スキャン別）。"""
        st = stat if stat is not None else self.stat
        st["n"] += 1
        st["sec"] += sec
        st["max"] = max(st["max"], sec)
        el = time.monotonic() - st["t"]
        if el < every or st["n"] == 0:
            return
        n = len(self.watch) if label == "固定" else len(self.scan)
        log.info("速度（%s %d銘柄）：読み取り1回 平均%.2f秒（最大%.2f秒）/ 値が動いた銘柄 1回あたり%.0f",
                 label, n, st["sec"] / st["n"], st["max"], st["changed"] / st["n"])
        st.update({"t": time.monotonic(), "n": 0, "sec": 0.0, "changed": 0, "max": 0.0})

    # ---- 適時開示（TDnet, R18） ----
    def _tdnet_alert(self, d, verdicts, elapsed: float):
        """開示1件の判定をアラートにして、記録と通知を直接行う（emit は売買代金で落とすので通さない）。"""
        from .models import Alert

        ts = datetime.now()
        name = d.name or self.names.get(d.code, "")
        cap = self.caps.get(d.code)
        cap_txt = f"時価総額 {cap / 1e8:,.0f}億円" if cap else "時価総額 不明"
        for v in verdicts:
            level = "買い" if v.buy else "参考"
            lines = [f"{ts:%H:%M:%S}", f"{d.code} {name}  {cap_txt}", f"[開示 {d.time}] {d.title}", v.summary,
                     d.pdf, f"（検知まで {elapsed:.1f}秒）"]
            a = Alert(ts, d.code, "R18", level, "\n".join(lines), 0.0,
                      {"kind": v.kind, "pdf": d.pdf, "title": d.title, **v.detail})
            with self.lock:
                self.count += 1
                self.recorder.alert(a)
            pop = "R18" in self.cfg.popup_rules or f"R18:{level}" in self.cfg.popup_rules
            self.pool.submit(self.notifier.send, a.message, pop, f"R18:{level}", ts)

    def _tdnet_loop(self, stop: threading.Event):
        """TDnet の一覧を poll_sec ごとに見て、新しい開示を判定する。監視の時間帯とは独立に start〜end で動く。"""
        from .kaiji import BigCaps, judge
        from .tdnet import TdnetWatcher, fetch, pdf_text

        t = self.cfg.tdnet
        w = TdnetWatcher(self.cfg.data_dir, t.newest_first, t.poll_sec)
        big, big_day = None, None
        start, end = _hm(t.start), _hm(t.end)
        log.info("適時開示（TDnet）を %.1f秒ごとに見ます（%s〜%s）", t.poll_sec, t.start, t.end)
        while not stop.is_set():
            now = datetime.now()
            if not (now.weekday() < 5 and start <= now.time() < end):
                time.sleep(20)
                continue
            if big is None or big_day != now.date() or (len(big.names) < 50 and self.caps):
                big = BigCaps.load(self.cfg.base_dir / t.bigcaps_file, self.caps, self.names, t.big_min_oku)
                big_day = now.date()
            t0 = time.monotonic()
            try:
                new = w.poll(now)
            except Exception as e:
                log.warning("TDnet 一覧の取得エラー: %s", e)
                time.sleep(5)
                continue
            for d in new:
                try:
                    st, pdf, _ = fetch(d.pdf, timeout=6)
                    body = pdf_text(pdf) if st == 200 else ""
                    vs = judge(d.code, d.title, body, big, self.caps.get(d.code), t.buyback_min_pct, t.small_max_oku)
                    if vs:
                        self._tdnet_alert(d, vs, time.monotonic() - t0)
                    else:
                        log.info("開示 %s %s %s 「%s」（判定なし）", d.time, d.code, d.name, d.title)
                except Exception as e:
                    log.warning("開示の判定エラー %s 「%s」: %s", d.code, d.title, e)
            time.sleep(max(0.05, t.poll_sec - (time.monotonic() - t0)))

    # ---- メインループ ----
    def run(self):
        start, end = _hm(self.cfg.session_start), _hm(self.cfg.session_end)
        waiting = False
        if self.cfg.tdnet.enabled:
            threading.Thread(target=self._tdnet_loop, args=(threading.Event(),), daemon=True, name="tdnet").start()
        while True:
            now = datetime.now()
            if not (now.weekday() < 5 and start <= now.time() < end):
                if not waiting:
                    log.info("時間外。%s〜%s の取引時間まで待機します", self.cfg.session_start, self.cfg.session_end)
                    waiting = True
                time.sleep(30)
                continue
            waiting = False
            try:
                self.setup_sheets()
            except Exception as e:
                log.warning("Excel/RSSに接続できません: %s（30秒後に再試行）", e)
                time.sleep(30)
                continue
            self.count = 0
            self.notifier.send(f"kane監視（楽天RSS）開始：固定{len(self.watch)}銘柄＋スキャン{len(self.scan)}銘柄"
                               + (f"（通知除外 {len(self.muted)}）" if self.muted else ""))
            stop = threading.Event()
            th = None
            if self.watch and self.cfg.rss.watch_poll_sec > 0:
                th = threading.Thread(target=self._watch_loop, args=(stop,), daemon=True, name="watch")
                th.start()
            while datetime.now().time() < end:
                t0 = time.monotonic()
                try:
                    self.poll()
                except Exception as e:  # Excelが閉じられた等
                    log.warning("RSS読み取りエラー: %s（再接続します）", e)
                    time.sleep(10)
                    try:
                        self.setup_sheets()
                    except Exception as e2:
                        log.warning("再接続失敗: %s", e2)
                    continue
                self._log_speed(time.monotonic() - t0)
                time.sleep(max(0.05, self.cfg.rss.poll_sec - (time.monotonic() - t0)))
            stop.set()
            if th:
                th.join(timeout=5)
            self.notifier.send(f"kane監視（楽天RSS）終了（本日の通知 {self.count}件）")
            time.sleep(60)
