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
| R1 | 浮動株回転率（出来高 ÷ 浮動株） | 50% 天井警戒 / 80% 急落警戒 / 95% 底候補 | 到達時に1回 |
| R2 | VWAP乖離 | +5% / +8% / +10%（2%戻ったら再通知可） | 到達時 |
| R3 | 高値圏の失速 | 高値−2%以内で1分出来高がピークの50%以下 | 1分足確定 |
| R4 | ダブルトップ | 2%押した後、高値−1%以内に再接近し5分出来高が前回高値時の50%以下 | 随時 |
| R5 | 板の偏り（上位5本 買/売） | 0.6以下 売り優勢 / 1.5以上 買い厚い（30秒継続） | 随時 |
| R6 | RSI(9)反落 | 90超え → 80割れ | 1分足確定 |
| R7 | 切り返し3条件 | 3%以上下げた後、安値更新なし2本＋直近3本が薄商い＋前足高値を1.5倍出来高で上抜け | 1分足確定 |
| R8 | 1回転反発の買い | 回転率95〜105%で大陰線（実体1%・出来高2倍）→ 3本以内に高値上抜け | ARM→BUY |
| R9 | 高値ブレイク | 10分以上前の高値を、5分出来高が閾値以上で上抜け | 随時 |

閾値は `config.toml` の `[rules]` で上書きできる（項目名は `kane/config.py` の `RuleConfig`）。
浮動株と R9 の5分出来高閾値は `symbols.csv`（`breakout_vol5m` が空なら浮動株の7%）。

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
