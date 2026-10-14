"""config.toml と symbols.csv の読み込み。"""
from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class RuleConfig:
    # R1 浮動株回転率
    turnover_levels: list[float] = field(default_factory=lambda: [0.5, 0.8, 0.95])
    # R2 VWAP乖離
    vwap_dev_levels: list[float] = field(default_factory=lambda: [0.05, 0.08, 0.10])
    vwap_dev_rearm: float = 0.02  # 閾値からこれだけ下がったら再通知可能
    # R3 失速
    stall_near_high: float = 0.02
    stall_vol_ratio: float = 0.5
    stall_peak_within_bars: int = 15
    # R4 ダブルトップ
    dtop_pullback: float = 0.02
    dtop_near: float = 0.01
    dtop_vol_ratio: float = 0.5
    # R5 板の偏り
    board_weak: float = 0.6
    board_strong: float = 1.5
    board_sustain_sec: int = 30
    # R6 RSI
    rsi_period: int = 9
    rsi_arm: float = 90.0
    rsi_fire: float = 80.0
    # R7 切り返し
    rebound_min_drawdown: float = 0.03
    rebound_window_bars: int = 30
    rebound_hold_bars: int = 2
    rebound_dry_ratio: float = 0.5
    rebound_vol_mult: float = 1.5
    # R8 1回転反発
    r8_turnover_low: float = 0.95
    r8_turnover_high: float = 1.05
    r8_min_body: float = 0.01
    r8_vol_mult: float = 2.0
    r8_expire_bars: int = 3
    # R9 高値ブレイク
    breakout_quiet_bars: int = 10
    breakout_default_vol5m_ratio: float = 0.07  # 浮動株に対する5分出来高の既定割合
    # R10 株価の段階（前日終値比）＋年初来高値更新
    price_step: float = 0.05
    price_step_down: bool = True  # 下落側（−5%, −10%…）も出す
    # R11 急騰・急落（1分前比）
    surge_1m: float = 0.02
    surge_cooldown_sec: int = 180
    # 共通
    cooldown_sec: int = 600
    board_cooldown_sec: int = 300


@dataclass
class SymbolInfo:
    code: str
    name: str
    float_shares: float | None
    breakout_vol5m: float | None = None
    issued_shares: float | None = None  # 時価総額の表示用
    ytd_high: float | None = None  # 前日までの年初来高値


@dataclass
class Config:
    base_url: str
    ws_url: str
    password_file: Path
    slack_webhook_file: Path | None
    slack_enabled: bool
    beep: bool
    data_dir: Path
    symbols: list[SymbolInfo]
    session_start: str
    session_end: str
    record_snapshots: bool
    rules: RuleConfig


def load_symbols(path: Path) -> list[SymbolInfo]:
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip()
            if not code or code.startswith("#"):
                continue

            def num(key):
                v = (row.get(key) or "").replace(",", "").strip()
                return float(v) if v else None

            out.append(
                SymbolInfo(
                    code=code,
                    name=(row.get("name") or "").strip(),
                    float_shares=num("float_shares"),
                    breakout_vol5m=num("breakout_vol5m"),
                    issued_shares=num("issued_shares"),
                    ytd_high=num("ytd_high"),
                )
            )
    return out


def load_config(path: str | Path = "config.toml") -> Config:
    path = Path(path)
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    base = path.parent

    def p(v):
        q = Path(v)
        return q if q.is_absolute() else base / q

    kabu = raw.get("kabu", {})
    slack = raw.get("slack", {})
    paths = raw.get("paths", {})
    session = raw.get("session", {})
    known = {f.name for f in fields(RuleConfig)}
    rules = RuleConfig(**{k: v for k, v in raw.get("rules", {}).items() if k in known})

    return Config(
        base_url=kabu.get("base_url", "http://localhost:18080/kabusapi"),
        ws_url=kabu.get("ws_url", "ws://localhost:18080/kabusapi/websocket"),
        password_file=p(kabu["password_file"]),
        slack_webhook_file=p(slack["webhook_file"]) if slack.get("webhook_file") else None,
        slack_enabled=slack.get("enabled", True),
        beep=raw.get("notify", {}).get("beep", False),
        data_dir=p(paths.get("data_dir", "data")),
        symbols=load_symbols(p(paths.get("symbols_csv", "symbols.csv"))),
        session_start=session.get("start", "08:55"),
        session_end=session.get("end", "15:35"),
        record_snapshots=raw.get("record", {}).get("snapshots", True),
        rules=rules,
    )
