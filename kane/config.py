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
    # R13 大口板（見えている板より桁違いに大きい板）の剥がれ予兆
    wall_mult: float = 10.0  # 周りの板（20本の中央値）の何倍以上か
    wall_min_yen: float = 50_000_000  # 板の金額（値段×数量）がこれ未満なら無視（5,000万円）
    wall_new_ratio: float = 0.5  # 直前の同じ値段の板がこの割合未満だった＝急に出た
    wall_cooldown_sec: int = 300
    wall_warn_ratio: float = 0.5  # 見張り中の大口板がピークのこの割合以下に減ったら「剥がれ予兆」
    wall_gone_ratio: float = 0.2  # この割合以下（または値段を突き抜けた）で「剥がれ」
    wall_notify_appear: bool = False  # 大口板が出たこと自体も通知するか
    wall_notify_gone: bool = True  # 剥がれ（消えた・突き抜けた）も通知するか
    ladder_levels: int = 3  # 連なり板：同じ量の板がこの本数以上、値段が連続して並んだら通知
    ladder_tol: float = 0.15  # 連なり板：各段の量の差がこの割合以内なら「同じ量」
    ladder_mult: float = 5.0  # 連なり板：各段が周りの板（中央値）の何倍以上か
    ladder_min_yen: float = 20_000_000  # 連なり板：合計金額の下限（2,000万円）
    depth_jump_ratio: float = 0.3  # 板の総量が1回の更新でこの割合以上 増えた／減ったら通知（同じ値段どうしで比較）
    depth_jump_min_yen: float = 20_000_000  # 増減分の金額の下限（2,000万円）
    depth_cooldown_sec: int = 120  # 同じ側の総量通知は2分に1回まで
    close_auction_from: str = "15:25"  # 引けオークションの開始（R16）
    close_imbalance_ratio: float = 0.3  # 成行の売り買い差が、板10本の片側合計のこの割合以上なら通知
    close_imbalance_min_yen: float = 20_000_000  # 成行の差の金額の下限（2,000万円）
    close_cooldown_sec: int = 60
    special_cooldown_sec: int = 20  # R17 特別気配：同じ向きの再発はこの秒数以内なら黙る（点滅よけ）
    # R14 ストップ高の剥がれ
    limit_warn_drop: float = 0.5  # 買い残がこの割合以下（直近のピーク比）になったら剥がれ警戒
    limit_warn_window_min: int = 10
    limit_warn_cooldown_sec: int = 180
    # 出来高の前提（バックテストで効いた組み合わせだけ通知する）
    # RVOL＝その時刻までの出来高 ÷（過去60日の平均日出来高 × その時刻までに普段出る出来高の割合）
    buy_alerts: bool = False  # 買い候補（全銘柄日・次の足で買う検証で優位性なし → 既定で出さない）
    buy_rvol_min: float = 2.0  # 年初来高値の更新 × RVOL 2〜10倍 → 買い候補
    buy_rvol_max: float = 10.0
    ytd_near: float = 0.02  # 年初来高値から+2%以内（抜けた直後）だけ
    top_rvol_min: float = 20.0  # VWAP乖離・失速・ダブルトップは RVOL 20倍以上のときだけ
    r2_min_level: float = 0.08  # VWAP乖離は+8%以上だけ
    fade_step: float = 0.25  # 前日比+25%以上 × RVOL 10倍以上 → 利確警戒
    fade_rvol_min: float = 10.0
    # R15 出来高の年初来記録（方向の合図ではなく「異常な注目」の知らせ）
    ytd_vol_alerts: bool = True  # 当日の出来高が今年の最大日出来高を超えた
    ytd_pace_alerts: bool = True  # この時刻までの出来高が、今年の最大日の「この時刻までの推定」を超えた
    ytd_pace_from: str = "09:05"  # ペース判定はこの時刻から（寄り直後は出来高の割合がぶれる）
    price_step_alerts: bool = False  # 5%刻みの段階通知（検証で優位性なし）を出すか
    # 時刻（9:00からの分）→ その時刻までに1日の出来高の何割が出るか（市場全体の平均）
    volume_profile: list = field(default_factory=lambda: [
        [0, 0.0], [5, 0.10], [15, 0.17], [30, 0.25], [60, 0.35], [150, 0.53],
        [210, 0.56], [270, 0.70], [330, 0.86], [390, 1.0]])
    # 共通
    cooldown_sec: int = 600


@dataclass
class TdnetConfig:
    """適時開示（TDnet）の見張り（R18）。監視の取引時間とは別の時間帯で動く。"""
    enabled: bool = True
    poll_sec: float = 1.0  # 一覧を見る間隔（秒）
    start: str = "08:00"  # 見張る時間帯（PTS夜間の材料になる 15:00〜 の開示も拾う）
    end: str = "18:30"
    newest_first: bool = True  # 一覧の先頭が最新か（python -m kane.tdnet --check で確認）
    buyback_min_pct: float = 5.0  # 自己株取得：発行済の何%以上で買い
    small_max_oku: float = 300  # 提携：開示した側の時価総額（億円）がこれ以下なら小型
    revision_min_pct: float = 20.0  # 業績修正：営業利益の増減率がこれ以上で買い
    yutai_min_yield_pct: float = 4.0  # 株主優待：優待利回り（100株）がこれ以上で買い
    followup_sec: float = 4.0  # 自己株の割合が出ないとき、時価総額・株価が読めるのを待って後追いする秒数
    big_min_oku: float = 10_000  # 提携：相手の時価総額（億円）がこれ以上なら大手（universe から自動で足す）
    bigcaps_file: str = "bigcaps.txt"  # 大手の名前（略称・海外）
    cap_unit: float = 1_000_000  # 楽天RSS「時価総額」の単位（百万円）


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
    poll_sec: float = 1.0  # スキャン銘柄（全銘柄）の読み取り間隔
    watch_poll_sec: float = 0.3  # 固定銘柄（板・成行）の読み取り間隔。別スレッドで回す
    function: str = "RssMarket"
    code_suffix: str = ".T"  # RssMarket に渡す銘柄コードの末尾（東証）
    board_levels: int = 10  # 固定監視銘柄で読む板の本数（0なら板を読まない）
    universe_csv: str = "universe.csv"  # 全体スキャン用の銘柄一覧（code,name）
    max_scan: int = 600
    # スキャン銘柄で通知するルール（固定銘柄は全ルール）
    scan_rules: list = field(default_factory=lambda: ["R2", "R3", "R4", "R10", "R14", "R15"])
    scan_min_value_yen: float = 100_000_000  # スキャン銘柄は売買代金がこれ未満なら通知しない
    # RssMarket の項目名（公式の関数一覧・数式登録エディタの表記に合わせて変更できる）
    items: dict = field(default_factory=lambda: {
        "price": "現在値", "volume": "出来高", "vwap": "VWAP", "open": "始値", "high": "高値",
        "low": "安値", "prev_close": "前日終値", "ytd_high": "年初来高値", "name": "銘柄名称",
        "value": "売買代金",  # VWAP が取れないときは 売買代金 ÷ 出来高 で計算する
        "bid_price": "最良買気配値{i}", "bid_qty": "最良買気配数量{i}",
        "ask_price": "最良売気配値{i}", "ask_qty": "最良売気配数量{i}",
        "bid_sign": "", "ask_sign": "",  # 気配の状態（特別気配）の項目名。空なら R12 は判定しない
        "mkt_buy": "成行買数量", "mkt_sell": "成行売数量", "cap": "時価総額",  # 引けオークション（15:25〜15:30）の成行。項目名が違えば check で分かる
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
    avg_vol: float | None = None  # 過去60営業日の平均日出来高（baseline.csv）
    ytd_max_vol: float | None = None  # 今年の最大日出来高（前日まで）
    ytd_max_date: str = ""
    loan: str = ""  # 貸借区分：1＝貸借銘柄（空売り可）、0＝信用銘柄（制度信用の売りなし）、空＝未確認
    mute: bool = False  # 1 なら通知しない（浮動株の一覧には残す）


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
    quiet_after: str | None = "15:25"  # この時刻以降はアラート窓・音を出さない（quiet_except のルールは例外）
    quiet_except: list = field(default_factory=lambda: ["R16", "R18"])  # 15:25以降でも出すルール（引けオークション・開示）
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    tdnet: TdnetConfig = field(default_factory=TdnetConfig)
    source: str = "kabu"  # "kabu" または "rss"
    rss: RssConfig = field(default_factory=RssConfig)
    base_dir: Path = Path(".")
    baseline: dict = field(default_factory=dict)  # 銘柄 → {"avg_vol", "ytd_max_vol", "ytd_max_date"}


def load_baseline(data_dir: Path) -> dict:
    p = data_dir / "baseline.csv"
    out = {}
    if p.exists():
        with open(p, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                def num(k):
                    try:
                        return float(r.get(k) or "")
                    except ValueError:
                        return None
                code = (r.get("code") or "").strip()
                if code:
                    out[code] = {"avg_vol": num("avg_vol"), "ytd_max_vol": num("ytd_max_vol"),
                                 "ytd_max_date": (r.get("ytd_max_date") or "").strip()}
    return out


def apply_baseline(info: "SymbolInfo", baseline: dict) -> "SymbolInfo":
    b = baseline.get(info.code) or {}
    info.avg_vol = b.get("avg_vol")
    info.ytd_max_vol = b.get("ytd_max_vol")
    info.ytd_max_date = b.get("ytd_max_date", "")
    return info


def load_profile(data_dir: Path) -> list | None:
    p = data_dir / "volume_profile.csv"
    if not p.exists():
        return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        rows = [[float(r["minute"]), float(r["frac"])] for r in csv.DictReader(f)]
    return rows or None


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
                    loan=(row.get("loan") or "").strip(),
                    mute=(row.get("mute") or "").strip() in ("1", "true", "yes"),
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
    data_dir = p(paths.get("data_dir", "data"))
    prof = load_profile(data_dir)
    if prof:
        rules.volume_profile = prof
    sknown = {f.name for f in fields(ScannerConfig)}
    scanner = ScannerConfig(**{k: v for k, v in raw.get("scanner", {}).items() if k in sknown})

    symbols = load_symbols(p(paths.get("symbols_csv", "symbols.csv")))
    baseline = load_baseline(data_dir)
    for sy in symbols:
        apply_baseline(sy, baseline)
    return Config(
        base_url=kabu.get("base_url", "http://localhost:18080/kabusapi"),
        ws_url=kabu.get("ws_url", "ws://localhost:18080/kabusapi/websocket"),
        password_file=p(kabu["password_file"]) if kabu.get("password_file") else None,
        slack_webhook_file=p(slack["webhook_file"]) if slack.get("webhook_file") else None,
        slack_enabled=slack.get("enabled", False),
        beep=raw.get("notify", {}).get("beep", False),
        data_dir=data_dir,
        symbols=symbols,
        session_start=session.get("start", "08:55"),
        session_end=session.get("end", "15:35"),
        record_snapshots=raw.get("record", {}).get("snapshots", True),
        rules=rules,
        popup_rules=raw.get("notify", {}).get("popup_rules", ["R13", "R14:剥がれ", "R14:警戒"]),
        feed=raw.get("notify", {}).get("feed", True),
        dialog=raw.get("notify", {}).get("dialog", False),
        quiet_after=raw.get("notify", {}).get("quiet_after", "15:25"),
        quiet_except=raw.get("notify", {}).get("quiet_except", ["R16", "R18"]),
        scanner=scanner,
        tdnet=TdnetConfig(**{k: v for k, v in raw.get("tdnet", {}).items() if k in {f.name for f in fields(TdnetConfig)}}),
        source=raw.get("source", {}).get("type", "kabu"),
        rss=_rss_config(raw.get("rss", {})),
        base_dir=base,
        baseline=baseline,
    )


def _rss_config(d: dict) -> RssConfig:
    rk = {f.name for f in fields(RssConfig)}
    cfg = RssConfig(**{k: v for k, v in d.items() if k in rk and k != "items"})
    cfg.items.update(d.get("items", {}))
    return cfg
