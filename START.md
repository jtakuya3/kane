# kane 起動手順（楽天RSS版）

フォルダ：`C:\Users\takuy\Desktop\08_開発案件\kane_git`

## 最短の起動（bat をダブルクリック）
`scripts\shortcut.bat` を一度ダブルクリックすると、デスクトップに「kane 朝 監視」「kane 夜 更新」「kane ライン」「kane 検証」「kane 答え合わせ」のショートカットができる。以後はそれをクリックするだけ。

| いつ | bat | やること |
|------|-----|---------|
| 朝（MS2にログイン → Excelで「RSS接続」のあと） | `scripts\morning.bat` | git pull → 監視を起動 |
| 夜（大引け後） | `scripts\night.bat` | git pull → 平均出来高の更新（約30分）→ 固定銘柄＋追加銘柄（bat 内の `EXTRA`）の乖離ライン表示 |
| 乖離ラインだけ見たい | `scripts\line.bat`（コードを付けると任意の銘柄：`line.bat 4498 3909`） | 30%・20%・15%ラインの株価 |
| 検証 | `scripts\backtest.bat`（`backtest.bat kisei` / `backtest.bat float` / `backtest.bat backtest`） | 早期検知・規制ライン・浮動株回転率・通常の検証 |
| 答え合わせ | `scripts\evaluate.bat` | 記録した通知の当たり率 |
| 銘柄一覧の更新 | `scripts\universe.bat` | JPX の data_j.xls から universe.csv を作る |

## 毎日の流れ
| いつ | やること | コマンド |
|------|---------|---------|
| 前日の夜（大引け後） | 平均出来高・今年の最大出来高を更新（約30分） | `py -3.11 -m kane.baseline daily` |
| 朝 8:50ごろ | ① マーケットスピードIIにログイン | － |
| | ② Excel を開き、楽天RSSのリボンで「RSS接続」 | － |
| | ③ 最新版にする | `git pull` |
| | ④ 監視を起動（落ちても30秒後に自動で再起動） | `scripts\start_monitor.bat` をダブルクリック |
| 監視中 | 画面右上のアラート窓を見る（15:25以降は表示しない） | － |
| 引け後 | 15:35に監視を終え、翌営業日の8:55まで自動で待機する（開いたままでよい）。止めるときは `Ctrl+C` → `Y` | － |

- 前日の夜にできなかったときは、朝の寄り付き前に `baseline daily` を実行する。
- 取引時間中に実行すると、今日の途中までの出来高は平均に入らない。

## PowerShellでまとめて実行する場合
```
cd C:\Users\takuy\Desktop\08_開発案件\kane_git
git pull
py -3.11 -m kane.monitor
```

## 初回だけ・ときどきやること
| やること | コマンド |
|---------|---------|
| 必要なライブラリを入れる（初回） | `scripts\install.bat` |
| 動作確認（RSSの値が読めるか・アラート窓のテスト表示・スキャンの読み取り秒数） | `scripts\check.bat` |
| 全銘柄の一覧を更新する（新規上場が増えたとき。JPXの data_j.xls を落としてから） | `py -3.11 -m kane.universe C:\Users\takuy\Downloads\data_j.xls` |
| 時刻ごとの出来高の配分を作る（一度だけ） | `py -3.11 -m kane.baseline profile "C:\Users\takuy\Downloads\_backtest_data\intraday_agg*.parquet"` |
| 通知の答え合わせ（4週間ほど記録がたまったら） | `py -3.11 -m kane.evaluate --all` |

## アラート窓の色
| 色 | 通知 |
|----|------|
| 赤（音つき） | R13 大口板（5,000万円以上かつ周りの10倍以上）が出た／見える範囲に入った／剥がれ予兆／剥がれ、R13 連なり板（同じ量×3段以上・合計2,000万円以上、例：1,143〜1,138円に8,000株×4）が出た／消えた、R14 ストップ高の剥がれ警戒・剥がれ。板は固定銘柄のみ |
| オレンジ | 天井警戒（R2 VWAP乖離+8%以上×出来高20倍、R3 失速、R4 ダブルトップ）、R10 利確警戒（+25%以上×出来高10倍） |
| 青 | R15 出来高の年初来更新・年初来ペース |
| 黒 | その他（張り付きなど） |

## うまく動かないとき
| 症状 | 対処 |
|------|------|
| 「Excelが起動していません」 | マーケットスピードIIにログインし、Excelで「RSS接続」してから起動し直す |
| 天井警戒・R15がまったく出ない | `kane_data\baseline.csv` がない。`baseline daily` を実行する |
| 「呼び出し先が呼び出しを拒否しました」 | 自動で待って再試行する。続く場合は Excel の操作をやめて待つ |
| 遅い（ログの「速度：読み取り1回 平均◯秒」が数秒以上） | `config.toml` の `max_scan` を下げるか、universe を市場で絞る（`--market グロース --market スタンダード`） |

## 記録の場所
`C:\Users\takuy\Desktop\08_開発案件\kane_data`
- `alerts_日付.csv`（通知）
- `bars_日付.csv`（1分足）
- `baseline.csv`（平均出来高）

## 運用ルール
- 浮動株（流通株）を調べた銘柄は、推定値でも必ず `symbols.csv` に追加する（`float_shares`・`issued_shares`）。推定は大株主からの逆算で、公式値が分かったら上書きする。
- `loan` 列＝貸借区分（1＝貸借銘柄、0＝信用銘柄、空＝未確認）。MS2 の銘柄情報の「貸借／信用」で確認して埋める。`backtest.bat float` が貸借／非貸借で分けて集計する。
