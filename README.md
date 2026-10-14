# kane — リアルタイム検出システム

kabuステーションAPIのPUSH配信から1分足を自前で作り、検出ルール R1〜R9 を判定して
Slack（無音）に通知、すべてを日次CSVに保存する。発注機能はない（通知と記録のみ）。

```
kabuステーション(PUSH) → kane.monitor → Engine(1分足生成 + R1〜R9) → Slack / 画面
                                     └→ data_dir/snapshots_*.csv  bars_*.csv  alerts_*.csv
録画CSV → kane.replay → 同じEngineで再判定（閾値の検証）
```

## 検出ルール
| # | 内容 | 既定の閾値 | タイミング |
|---|---|---|---|
| R1 | 浮動株回転率（出来高 ÷ 浮動株） | 40% 天井警戒 / 90% 底候補（50%・100%だと出遅れるため早め） | 到達時に1回 |
| R2 | VWAP乖離 | +5% / +8% / +10%（2%戻ったら再通知可） | 到達時 |
| R3 | 高値圏の失速 | 高値−2%以内で1分出来高がピークの50%以下 | 1分足確定 |
| R4 | ダブルトップ | 2%押した後、高値−1%以内に再接近し5分出来高が前回高値時の50%以下 | 随時 |
| R9 | 高値ブレイク | 10分以上前の高値を、5分出来高が閾値以上で上抜け | 随時 |
| R10 | 株価の段階・年初来高値更新 | 前日終値比 ±5%刻みの段階を初めて超えた／年初来高値を初めて更新 | 随時 |
| R13 | 大口板（ポップアップあり） | 板20本の中央値の10倍以上・5,000万円以上の板が、直前まで見えていた範囲の中の、板が無かった（または半分未満だった）値段に急に出た。株価が動いて既存の板が見えてきただけの場合は出さない（寄り前・昼休み・特別気配中は除外） | 随時 |
| R14 | ストップ高（張り付き・剥がれ警戒・剥がれ・再張り付き） | 買い残が10分内ピークの50%以下、または上限値の売り板≧買い残で警戒（ポップアップあり） | 随時 |

R10・R13・R14 は時刻・銘柄・時価総額の見出し付きの複数行で通知する。
時価総額は `symbols.csv` の `issued_shares`、年初来高値は `ytd_high`（前日までの値）を使う。空欄なら省略。

閾値は `config.toml` の `[rules]` で上書きできる（項目名は `kane/config.py` の `RuleConfig`）。
浮動株と R9 の5分出来高閾値は `symbols.csv`（`breakout_vol5m` が空なら浮動株の7%）。

## 取り込み元
`config.toml` の `[source] type` で切り替える。

- `"rss"`（現在の既定）：楽天 マーケットスピードII RSS。kane が起動中の Excel にシート
  `kane_watch`（固定銘柄・板10本）と `kane_scan`（universe.csv の銘柄・最良気配のみ）を作って
  `RssMarket` 関数を書き込み、1秒ごとに値を読む。スキャン銘柄は `[rss] scan_rules` のルールだけ、
  売買代金が `scan_min_value_yen` 以上のときに通知する。
- `"kabu"`：kabuステーションAPI（PUSH配信＋ランキングで50枠を入れ替え）。Professionalプラン以上が必要。

スキャン用の銘柄一覧は JPX の上場銘柄一覧（data_j.xls）から作る：
```
python -m kane.universe C:/Users/takuy/Downloads/data_j.xls --market グロース --market スタンダード
```

## 監視銘柄（kabu：固定＋ランキング）
- `symbols.csv` の銘柄は**固定**で常にPUSH登録する。`group` 列（security / ipo など）は開始通知の表示用。
- 残りの枠（50 − 固定数）は、kabuのランキングAPI（値上がり率・売買高急増・売買代金急増・TICK回数など、
  `[scanner] rankings`）を10秒ごとに巡回して、順位を点数化した上位で自動的に埋める。
  一度入れた銘柄は最低10分は外さない。
- PUSH枠に入っていないランキング銘柄も、ランキングの株価で R10（段階）・R11（急騰・急落）を判定する
  （起動直後の1回目は現在の段階を覚えるだけで通知しない）。

## セットアップ（Windows）
1. `git clone` / `git pull` して、このフォルダで `py -3.11 -m pip install -r requirements.txt`
2. `config.toml` のパスを確認（APIパスワード・Slack Webhookは既存の Downloads のファイルを読む）
3. kabuステーションを起動・ログイン（API有効）
4. `scripts\check.bat` で接続確認（トークン・PUSH登録・現在の回転率が出ればOK）
5. `scripts\start_monitor.bat` で監視開始（落ちても30秒後に再起動、時間外は待機）

PUSH登録は起動時に `unregister/all` してから行う（上限50銘柄）。

## 検証
```
python -m kane.replay C:/Users/takuy/Desktop/08_開発案件/kane_data/snapshots_20261015.csv
python -m pytest
```

## 答え合わせ（判定の当たり率）
- 毎日のライブ記録：`python -m kane.evaluate --date 20261015`（`--all` で全日を合算）。
  各通知の1・5・15・30分後のリターンと15分以内の伸び／逆行を測り、ルールごとの当たり率を出す。
- 過去データ（バックテスト）：`py -3.11 -m pip install -r requirements-backtest.txt` の後
  ```
  python -m kane.backtest --inspect "C:/Users/takuy/Downloads/_backtest_data/min1_xxx.parquet"   # 列の確認
  python -m kane.backtest "C:/Users/takuy/Downloads/_backtest_data/min1*.parquet"                # 実行
  ```
  前日比±5%以上動いた銘柄日を対象に、ライブと同じエンジンで判定し、
  `data_dir/backtest_日時/` に eval.csv・evalsum.csv・turnover_study.csv（高値・安値が当日出来高の何%時点か）を保存する。
  元データは読むだけで書き換えない。板のデータは無いので R13・R14 は評価できない。
