"""画面のアラート窓：通知を最前面の小さな窓に新しい順で流す（tkinter・別スレッド）。

注文操作の邪魔にならないよう、フォーカスは奪わない。重要なルール（popup_rules）は赤で強調する。
"""
from __future__ import annotations

import logging
import queue
import re
import threading
from datetime import datetime

log = logging.getLogger("kane")

# ルール → (背景色, 文字色)
COLORS = {
    "important": ("#c62828", "#ffffff"),  # 大口板・ストップ高など popup_rules
    "buy": ("#1b5e20", "#ffffff"),  # R9 高値ブレイク
    "warn": ("#e65100", "#ffffff"),  # R2 VWAP乖離 / R3 失速 / R4 ダブルトップ
    "info": ("#1e1e1e", "#e0e0e0"),
}
BUY_RULES = {"R9"}
WARN_RULES = {"R2", "R3", "R4"}


def color_key(rule: str, important: bool) -> str:
    if important:
        return "important"
    if rule in BUY_RULES:
        return "buy"
    if rule in WARN_RULES:
        return "warn"
    return "info"


class AlertFeed:
    def __init__(self, max_items: int = 300):
        self.q: queue.Queue = queue.Queue()
        self.max_items = max_items
        self.ok = True
        threading.Thread(target=self._run, daemon=True).start()

    def push(self, text: str, rule: str = "", important: bool = False):
        if self.ok:
            self.q.put((datetime.now(), text, color_key(rule, important)))

    def _run(self):
        try:
            import tkinter as tk
        except Exception as e:
            log.warning("アラート窓を開けません（tkinterなし）: %s", e)
            self.ok = False
            return
        try:
            root = tk.Tk()
        except Exception as e:  # 画面が無い環境
            log.warning("アラート窓を開けません: %s", e)
            self.ok = False
            return
        root.title("kane アラート")
        root.geometry("560x420-10+10")  # 右上
        root.attributes("-topmost", True)
        root.configure(bg="#111111")
        text = tk.Text(root, wrap="word", bg="#111111", fg="#e0e0e0", font=("Meiryo", 10),
                       borderwidth=0, padx=6, pady=4)
        text.pack(fill="both", expand=True)
        for key, (bg, fg) in COLORS.items():
            text.tag_configure(key, background=bg, foreground=fg, spacing1=4, spacing3=4)
        text.tag_configure("sep", foreground="#444444")
        text.configure(state="disabled")
        count = [0]

        def poll():
            try:
                while True:
                    ts, msg, key = self.q.get_nowait()
                    text.configure(state="normal")
                    text.insert("1.0", "─" * 40 + "\n", "sep")
                    body = msg if re.match(r"\d{2}:\d{2}:\d{2}", msg) else f"{ts:%H:%M:%S} {msg}"
                    text.insert("1.0", body + "\n", key)
                    count[0] += 1
                    if count[0] > self.max_items:  # 古いものを消す
                        text.delete(f"{self.max_items * 8}.0", "end")
                    text.configure(state="disabled")
                    if key == "important":
                        root.bell()
            except queue.Empty:
                pass
            root.after(200, poll)

        root.after(200, poll)
        root.mainloop()
