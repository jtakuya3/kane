"""config.toml と symbols.csv の読み込み。"""
from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class RuleConfig:
    # R1 浮動株回転率
    turnover_levels: list[float] = field(default_factory=lambda: [0.4, 0.9])
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
    # R9 高値ブレイク
    breakout_quiet_bars: int = 10
    breakout_default_vol5m_ratio: float = 0.07  # 浮動株に対する5分出来高の既定割合
    # R10 株価の段階（前日終値比）＋年初来高値更新
    price_step: float = 0.05
    price_step_down: bool = True  # 下落側（−5%, −10%…）も出す
    # R13 大口板（見えている板より桁違いに大きい板が急に出た）
    wall_mult: float = 10.0  # 周りの板（20本の中央値）の何倍以上か
    wall_min_yen: float = 50_000_000  # 板の金額（値段×数量）がこれ未満なら無視（5,000万円）
    wall_new_ratio: float = 0.5  # 直前の同じ値段の板がこの割合未満だった＝急に出た
    wall_cooldown_sec: int = 300
    # R14 ストップ高の剥がれ
    limit_warn_drop: float = 0.5  # 買い残がこの割合以下（直近のピーク比）になったら剥がれ警戒
    limit_warn_window_min: int = 10
    limit_warn_cooldown_sec: int = 180
    # 共通
    cooldown_sec: int = 600


@dataclass
class ScannerConfig:
    enabled: bool = True
    interval_sec: float = 10.0
    call_gap_sec: float = 0.2  # ランキングAPIの呼び出し間隔（1秒10回の制限より十分ゆっくり）
    max_push: int = 50
    min_hold_sec: int = 600  # 入れた銘柄は最低この時間は外さない
    keep_zone: float = 1.5  # 空き枠×この倍率の順位以内なら入れたままにする
    light_alerts: bool = True  # PUSH未登録の銘柄もランキングの株価でR10・R11を判定
    # [種類, 市場]。種類 1値上がり率 2値下がり率 3売買高 4売買代金 5TICK回数 6売買高急増 7売買代金急増
    # 市場 ALL 全市場 / TP プライム / TS スタンダード / TG グロース
    rankings: list = field(default_factory=lambda: [
        [1, "ALL"], [6, "ALL"], [7, "ALL"], [5, "ALL"], [1, "TG"], [1, "TS"], [2, "ALL"],
    ])
    weights: dict = field(default_factory=lambda: {
        "1": 1.0, "2": 0.5, "3": 0.5, "4": 0.5, "5": 0.8, "6": 1.2, "7": 1.0,
    })


@dataclass
class RssConfig:
    """楽天 マーケットスピードII RSS（Excel）から読む場合の設定。"""
    workbook: str = "kane_rss.xlsx"
    poll_sec: float = 1.0
    function: str = "RssMarket"
    code_suffix: str = ".T"  # RssMarket に渡す銘柄コードの末尾（東証）
    board_levels: int = 10  # 固定監視銘柄で読む板の本数（0なら板を読まない）
    universe_csv: str = "universe.csv"  # 全体スキャン用の銘柄一覧（code,name）
    max_scan: int = 600
    # スキャン銘柄で通知するルール（固定銘柄は全ルール）
    scan_rules: list = field(default_factory=lambda: ["R10", "R14"])
    scan_min_value_yen: float = 100_000_000  # スキャン銘柄は売買代金がこれ未満なら通知しない
    # RssMarket の項目名（公式の関数一覧・数式登録エディタの表記に合わせて変更できる）
    items: dict = field(default_factory=lambda: {
        "price": "現在値", "volume": "出来高", "vwap": "VWAP", "open": "始値", "high": "高値",
        "low": "安値", "prev_close": "前日終値", "ytd_high": "年初来高値", "name": "銘柄名称",
        "value": "売買代金",  # VWAP が取れないときは 売買代金 ÷ 出来高 で計算する
        "bid_price": "最良買気配値{i}", "bid_qty": "最良買気配数量{i}",
        "ask_price": "最良売気配値{i}", "ask_qty": "最良売気配数量{i}",
        "bid_sign": "", "ask_sign": "",  # 気配の状態（特別気配）の項目名。空なら R12 は判定しない
    })
    special_values: list = field(default_factory=lambda: ["特", "S", "特別気配"])
    value_unit: float = 1000  # 楽天RSSの売買代金は千円単位


@dataclass
class SymbolInfo:
    code: str
    name: str
    float_shares: float | None
    breakout_vol5m: float | None = None
    issued_shares: float | None = None  # 時価総額の表示用
    ytd_high: float | None = None  # 前日までの年初来高値
    group: str = ""  # 固定監視のグループ名（ipo / security など）


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
    popup_rules: list = field(default_factory=lambda: ["R13", "R14:剥がれ", "R14:警戒"])
    feed: bool = True  # 画面のアラート窓に全通知を流す
    dialog: bool = False  # popup_rules の通知でメッセージボックスも出す
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    source: str = "kabu"  # "kabu" または "rss"
    rss: RssConfig = field(default_factory=RssConfig)
    base_dir: Path = Path(".")


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
                    group=(row.get("group") or "").strip(),
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
    sknown = {f.name for f in fields(ScannerConfig)}
    scanner = ScannerConfig(**{k: v for k, v in raw.get("scanner", {}).items() if k in sknown})

    return Config(
        base_url=kabu.get("base_url", "http://localhost:18080/kabusapi"),
        ws_url=kabu.get("ws_url", "ws://localhost:18080/kabusapi/websocket"),
        password_file=p(kabu["password_file"]) if kabu.get("password_file") else None,
        slack_webhook_file=p(slack["webhook_file"]) if slack.get("webhook_file") else None,
        slack_enabled=slack.get("enabled", True),
        beep=raw.get("notify", {}).get("beep", False),
        data_dir=p(paths.get("data_dir", "data")),
        symbols=load_symbols(p(paths.get("symbols_csv", "symbols.csv"))),
        session_start=session.get("start", "08:55"),
        session_end=session.get("end", "15:35"),
        record_snapshots=raw.get("record", {}).get("snapshots", True),
        rules=rules,
        popup_rules=raw.get("notify", {}).get("popup_rules", ["R13", "R14:剥がれ", "R14:警戒"]),
        feed=raw.get("notify", {}).get("feed", True),
        dialog=raw.get("notify", {}).get("dialog", False),
        scanner=scanner,
        source=raw.get("source", {}).get("type", "kabu"),
        rss=_rss_config(raw.get("rss", {})),
        base_dir=base,
    )


def _rss_config(d: dict) -> RssConfig:
    rk = {f.name for f in fields(RssConfig)}
    cfg = RssConfig(**{k: v for k, v in d.items() if k in rk and k != "items"})
    cfg.items.update(d.get("items", {}))
    return cfg
