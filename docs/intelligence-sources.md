# 投資エージェント 情報ソース全リスト

5人のエージェントが共通で確認する情報源の完全リスト。
すべて公開情報（OSINT）またはフリーAPI。

---

## 1. 地政学・軍事OSINT

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **Shadowbroker** | 空母位置、軍用機、衛星、GPS妨害、船舶追跡 | REST API (自己ホスト) | 軍事エスカレーション→原油、防衛銘柄 |
| **GDELT Project** | 世界のニュース/紛争をリアルタイム解析 | gdeltproject.org API (無料) | 地政学リスクの定量化 |
| **ACLED** | 紛争・抗議活動データベース | acleddata.com API | 新興国リスク、サプライチェーン断絶 |
| **LiveUAMap** | ウクライナ/中東/紛争マップ | Web scraping | 紛争進展→エネルギー、穀物 |
| **SIPRI** | 軍事費・武器取引データ | sipri.org | 防衛セクター長期トレンド |
| **Nuclear Threat Initiative** | 核関連動向 | nti.org | 極端なテールリスク監視 |

---

## 2. 衛星画像・リモートセンシング

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **Sentinel Hub** | EU Copernicus衛星画像（無料枠あり） | sentinelhub.com API | 農作物状況、工場稼働、洪水被害 |
| **NASA FIRMS** | 世界の火災ホットスポット（15分更新） | firms.modaps.eosdis.nasa.gov | 農業被害→穀物先物、保険 |
| **NASA Worldview/GIBS** | 衛星画像タイルサービス | gibs.earthdata.nasa.gov | 大気汚染=工場稼働の代理指標 |
| **Planet (Explorer)** | 高解像度衛星画像（一部無料） | planet.com | 小売駐車場、港湾コンテナ量 |
| **Google Earth Engine** | 衛星データ解析プラットフォーム | earthengine.google.com | 長期的環境/経済変化の検出 |

---

## 3. 船舶・物流・サプライチェーン

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **MarineTraffic** | 船舶AIS追跡 | marinetraffic.com API | 貿易量、港湾渋滞、原油タンカー動態 |
| **AISstream.io** | リアルタイムAIS WebSocket | aisstream.io (無料, OpenAPI 3.0対応) | 船舶リアルタイム追跡 |
| **AISViz** | AISデータ抽出/処理/可視化 | github.com/AISViz (OSS) | NOAA連携、カスタム分析 |
| **Global Fishing Watch** | 港湾訪問、漁業、滞留、AISギャップ検知 | globalfishingwatch.org API (無料キー) | 海洋経済活動、制裁回避検知 |
| **Freightos Baltic Index** | コンテナ運賃指数 | fbx.freightos.com | 物流コスト→小売/製造業マージン |
| **Port of LA/Long Beach** | 米国最大港のコンテナ処理量 | portoflosangeles.org | 米国輸入量の先行指標 |
| **Flexport Ocean Timeliness** | 海上輸送遅延指標 | flexport.com | サプライチェーンボトルネック |
| **Drewry WCI** | 世界コンテナ運賃指数 | drewry.co.uk | 海運セクター、グローバル貿易 |
| **OpenSky Network** | 航空機リアルタイム追跡 | opensky-network.org API | 航空需要、プライベートジェット（経営者動向） |

---

## 4. マクロ経済指標

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **FRED (Federal Reserve)** | 米国経済指標800,000+系列 | fred.stlouisfed.org API (無料) | 金利、インフレ、雇用、GDP |
| **e-Stat** | 日本政府統計ポータル | e-stat.go.jp API | 日本のマクロ経済 |
| **World Bank Open Data** | 世界各国経済データ | data.worldbank.org API | 新興国マクロ |
| **IMF Data** | 国際通貨基金データ | data.imf.org | 国際収支、為替リスク |
| **OECD Data** | 先進国経済指標 | data.oecd.org API | 先進国比較分析 |
| **Trading Economics** | 各国経済カレンダー | tradingeconomics.com | イベントドリブン投資 |

---

## 5. 中央銀行・金融政策

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **FedWatch (CME)** | FF金利先物から利下げ/利上げ確率 | cmegroup.com | 金利予想の市場コンセンサス |
| **Fed Speeches** | FRB理事の講演テキスト | federalreserve.gov RSS | タカ派/ハト派シグナル |
| **日銀金融政策決定会合** | 日銀議事録・声明 | boj.or.jp | 円金利、日本株 |
| **ECB Publications** | 欧州中央銀行公開資料 | ecb.europa.eu | ユーロ圏金融政策 |
| **Treasury Yield Curve** | イールドカーブ（逆イールド監視） | treasury.gov / FRED | 景気後退の先行指標 |

---

## 6. SEC/規制当局ファイリング

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **SEC EDGAR** | 全上場企業のファイリング | sec.gov EDGAR API (無料) | 10-K, 10-Q, 8-K, 13F |
| **EdgarTools** | SEC Filing構造化パーサー | `pip install edgartools` (MIT, APIキー不要) | Form 3/4/5を構造化Pythonオブジェクトで取得 |
| **SEC Form 4** | インサイダー取引報告 | sec.gov / openinsider.com | 経営者の売買=最強のシグナル |
| **Earnings Feed API** | SEC Filing高速配信（60秒以内） | earningsfeed.com/api (無料枠: 15req/min) | リアルタイムFiling検知 |
| **13F Filing** | 機関投資家のポジション（四半期） | whalewisdom.com / sec.gov | バフェット等の売買追跡 |
| **Schedule 13D/G** | 5%以上の大量保有報告 | sec.gov | アクティビスト参入の検知 |
| **EDINET** | 日本の有価証券報告書 | edinet-fsa.go.jp API | 日本株ファンダメンタルズ |
| **大量保有報告書** | 日本版13D | edinet-fsa.go.jp | 日本株の大口動向 |

---

## 7. 政治・ロビイング・議会

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **Capitol Trades** | 米国議員の株式取引 | capitoltrades.com (無料ダッシュボード) | 議員は法律を作る側=究極のインサイダー |
| **Quiver Quantitative** | 議員取引、ロビイング、政府契約を統合 | quiverquant.com (無料ダッシュボード, API $10/mo, Python SDK on GitHub) | 政策→銘柄の紐付け |
| **GovGreed** | 188K+議会取引、法案MLスコアリング | govgreed.com/api (2026夏ローンチ、30日無料) | 法案→銘柄インパクトのML予測 |
| **OpenSecrets** | 政治献金、ロビイングデータ | opensecrets.org API | 規制変更の先行指標 |
| **Congress.gov** | 法案の進捗追跡 | congress.gov API | 法案成立→業界インパクト |
| **Federal Register** | 米国連邦規制の公告 | federalregister.gov API | 新規制の影響分析 |

---

## 8. 特許・技術動向

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **USPTO PatentsView** | 米国特許データ | patentsview.org API (無料) → 2026/3 ODP移行中 | 技術的優位性の定量化 |
| **USPTO Open Data Portal** | 特許ファイルラッパー、譲渡、商標 | developer.uspto.gov (複数の無料API) | 特許出願・譲渡のリアルタイム追跡 |
| **EPO Open Patent Services** | 欧州特許データ、法的状態、特許ファミリー | ops.epo.org (無料XML API) | 欧州企業の技術力 |
| **Google Patents** | 世界の特許検索 | patents.google.com | 競合分析 |
| **J-PlatPat** | 日本の特許検索 | j-platpat.inpit.go.jp | 日本企業の技術力 |
| **Lens.org** | 特許+学術論文の統合検索 | lens.org API | 研究→特許→製品のパイプライン |
| **WIPO PATENTSCOPE** | PCT国際出願、1億件超の特許文書 | patentscope.wipo.int (無料検索) | グローバル特許トレンド |

---

## 9. オルタナティブ経済指標（リアルタイム）

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **Google Trends** | 検索ボリュームの変化 | trends.google.com (非公式API) | 消費者関心の先行指標 |
| **Indeed/Glassdoor求人数** | 業種別求人動向 | indeed.com / glassdoor.com | 雇用の先行指標、企業の成長期待 |
| **App Annie / Sensor Tower** | アプリDL数ランキング | data.ai | SaaS/テック企業の成長追跡 |
| **NextLabs / AppVector** | App Storeランキング追跡 | nextlabs.io (無料200キーワード/日) | アプリ成長のリアルタイム監視 |
| **42matters** | アプリメタデータ、DL推定、トップチャート | 42matters.com (14日無料トライアル) | Google Play/Apple/Amazon横断分析 |
| **SimilarWeb** | ウェブトラフィック推定 | similarweb.com (一部無料) | EC/SaaS企業の利用動向 |
| **Glassdoor企業レビュー** | 従業員の満足度変化 | glassdoor.com | 内部崩壊の早期検知 |
| **GitHub Star/Commit推移** | OSSプロジェクトの活性度 | github.com API | テック企業の開発者エコシステム |
| **Stack Overflow Trends** | 技術の人気推移 | insights.stackoverflow.com | 技術トレンドの定量化 |
| **Yelp/Google Reviews** | 店舗評価の変化 | yelp.com/google API | 小売/飲食チェーンの業績先行指標 |
| **電力消費データ** | 地域別電力需要 | IODA / 各電力会社 | 工場稼働率の代理指標 |
| **大気汚染データ (PM2.5)** | NO2/PM2.5のリアルタイム測定 | aqicn.org API (無料) | 中国の工場稼働の代理指標 |
| **夜間光データ** | 衛星から見た夜間の明るさ | NASA Black Marble | 経済活動レベルの推定（新興国に有効） |

---

## 10. マーケットマイクロストラクチャー

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **Unusual Whales** | 異常オプションフロー検知 | unusualwhales.com/public-api (100+エンドポイント) | スマートマネーの動き |
| **Intrinio Options** | 異常オプションアクティビティ | docs.intrinio.com (無料枠あり) | 全オプションチェーンの異常検知 |
| **CBOE Options Data** | Put/Call Ratio、VIX先物 | cboe.com | 市場センチメント |
| **FINRA Short Interest** | 空売り残高（隔週更新） | finra.org | ショートスクイーズ候補 |
| **FINRA OTC Transparency** | ダークプール取引量（週次） | otctransparency.finra.org (無料) / developer.finra.org | 機関投資家の動向（2-4週遅延） |
| **Stockgrid** | ダークプール可視化 | stockgrid.io/darkpools (無料ダッシュボード) | ダークプールネットポジション |
| **Whale Alert** | 暗号通貨の大口送金 | whale-alert.io API (無料枠) | クジラの売買=暗号市場の先行指標 |
| **ClankApp** | 20+チェーンの大口取引インデックス | clankapp.com API (無料) | マルチチェーン暗号クジラ追跡 |
| **Arkham Intelligence** | 8億+ウォレットラベル、マルチチェーン | arkham.com (無料枠) | 取引所/ファンドの暗号通貨フロー |
| **Glassnode** | オンチェーン分析（一部無料） | glassnode.com | 暗号通貨のファンダメンタルズ |
| **Fear & Greed Index** | CNN市場恐怖/貪欲指数 | money.cnn.com | 極端な恐怖=逆張り買いシグナル |

---

## 11. ソーシャルセンチメント

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **X (Twitter) API** | 銘柄言及量・感情分析 | x.com API | リテール投資家のセンチメント |
| **Reddit (r/wallstreetbets等)** | ミーム株・個人投資家の動向 | reddit.com API | ミーム株候補の早期検知 |
| **Stocktwits** | 株式特化SNS | stocktwits.com API | 銘柄別のブル/ベア比率 |
| **Discord/Telegram** | 暗号通貨コミュニティ | Bot API | 暗号通貨のポンプ検知 |
| **Earnings Call Transcripts** | 決算説明会の文字起こし | seekingalpha.com / finnhub | 経営者の言葉遣いの変化（NLP分析） |
| **Glassdoor CEO Rating** | CEO支持率の変化 | glassdoor.com | 経営陣への信頼の変化 |

---

## 12. 気象・自然災害

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **NOAA Weather** | 米国気象データ | weather.gov API (無料) | 農業、エネルギー需要 |
| **USGS Earthquake** | 地震リアルタイム | earthquake.usgs.gov API | 保険、インフラ、サプライチェーン |
| **NOAA Space Weather** | 太陽フレア、磁気嵐 | swpc.noaa.gov | 衛星/通信障害リスク |
| **Copernicus Climate** | 欧州気候データ | climate.copernicus.eu | 農業、エネルギー長期トレンド |
| **旱魃モニター (US)** | 米国旱魃状況 | droughtmonitor.unl.edu | 穀物先物、水関連銘柄 |
| **ハリケーン追跡** | 熱帯低気圧の予測進路 | nhc.noaa.gov | エネルギー（メキシコ湾）、保険 |

---

## 13. 暗号通貨特化

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **CoinGecko** | 暗号通貨価格/時価総額 | coingecko.com API (無料) | 基本データ |
| **DefiLlama** | DeFi TVL（預かり資産）追跡 | defillama.com API (無料) | DeFiプロトコルの健全性 |
| **Dune Analytics** | オンチェーンデータのSQL分析 | dune.com (無料枠) | カスタムオンチェーン分析 |
| **Token Unlocks** | トークンのロック解除スケジュール | token.unlocks.app | 売り圧力の予測 |
| **L2Beat** | L2ネットワークのTVL/トランザクション | l2beat.com | Ethereum L2エコシステム |
| **Santiment** | オンチェーン+ソーシャルデータ統合 | santiment.net (一部無料) | 暗号通貨のオルタナティブデータ |

---

## 14. 企業ファンダメンタルズ

| ソース | 内容 | API/ツール | 投資への影響 |
|--------|------|-----------|-------------|
| **Yahoo Finance** | 株価、財務諸表、アナリスト予想 | yfinance Python (無料) | 基本データ |
| **Financial Modeling Prep** | 財務諸表API | financialmodelingprep.com | DCF分析、比較分析 |
| **Alpha Vantage** | 株価、テクニカル指標 | alphavantage.co (無料) | テクニカル分析 |
| **Finnhub** | 株価+オルタナティブデータ統合 | finnhub.io (無料枠) | 統合データプラットフォーム |
| **SimFin** | クリーンな財務データ | simfin.com API (無料) | ファンダメンタルズ分析 |
| **Macrotrends** | 長期財務データ | macrotrends.net | 10年以上の財務トレンド |

---

## カテゴリ別ベスト無料ツール（実装優先順）

| カテゴリ | ベスト無料ツール | 備考 |
|---------|-----------------|------|
| SEC インサイダー取引 | **EdgarTools** (`pip install edgartools`, MIT, APIキー不要) | Form 3/4/5を構造化取得 |
| ダークプール | **FINRA OTC Transparency** (otctransparency.finra.org) | 2-4週遅延だが無料 |
| 議員取引 | **Capitol Trades** (capitoltrades.com) | 無料ダッシュボード |
| 特許監視 | **USPTO Open Data Portal** (developer.uspto.gov) | 複数の無料API |
| 求人/雇用 | **FRED API** + **BLS API** (共に無料) | JOLTS含む |
| App Storeランキング | **NextLabs** (nextlabs.io, 200キーワード/日無料) | Google Sheetsアドオン |
| 船舶/港湾 | **aisstream.io** (無料WebSocket API) | リアルタイムAIS |
| 衛星画像 | **Sentinel Hub** (sentinelhub.com, 無料枠) | 10m解像度 |
| オプションフロー | **Intrinio** (docs.intrinio.com, 無料枠) | 異常アクティビティAPI |
| 暗号クジラ | **ClankApp** (clankapp.com, 無料API) | 20+チェーン対応 |
| マクロ経済 | **FRED** (fred.stlouisfed.org, 840K+系列) | 最重要インフラ |
| 地政学OSINT | **Shadowbroker** (自己ホスト) | Docker一発デプロイ |

---

## エージェント別の重点情報ソース

```
ELON（逆張り集中）
  最重要：Fear & Greed Index, VIX, Short Interest,
          Google Trends（パニック検知）, Space Weather
  ↓
  「恐怖が最大のとき、みんなが見ていないデータに真実がある」

DARIO（リスク管理）
  最重要：Treasury Yield Curve, FRED全指標, Options P/C Ratio,
          ACLED紛争データ, ドローダウン監視
  ↓
  「リスクを数値化できないなら、投資してはいけない」

STEVE（プロダクト直感）
  最重要：App Store Rankings, GitHub Stars, Glassdoor Reviews,
          Google Trends（製品名）, SimilarWeb
  ↓
  「数字の前に、プロダクトを触れ」

PETER（OSINT逆張り）
  最重要：★Shadowbroker全データ, 衛星画像, 船舶追跡,
          特許データ, 議員取引, 大気汚染データ
  ↓
  「誰も見ていない情報に、誰も気づいていない真実がある」

JEFF（キャッシュフロー重視）
  最重要：SEC EDGAR (10-K/10-Q), 求人データ, Freightos運賃,
          港湾データ, Earnings Transcripts
  ↓
  「フライホイールが回っているか？ 数字が証明しているか？」
```

---

## 情報パイプラインの優先度

### Tier 1: リアルタイム（60秒以内に反映）
- 株価/出来高（Yahoo Finance）
- VIX / Fear & Greed
- 暗号通貨価格（CoinGecko）
- Whale Alert（大口暗号送金）
- 船舶AIS（Shadowbroker）
- 軍用機追跡（Shadowbroker）

### Tier 2: 時間単位（1-6時間ごと更新）
- ニュースフィード（GDELT, NewsAPI）
- Xセンチメント分析
- 異常オプションフロー
- GPS妨害ゾーン変化
- 火災ホットスポット（NASA FIRMS）
- 地震（USGS）

### Tier 3: 日次
- マクロ経済指標（FRED）
- App Storeランキング変動
- 求人数変化
- 大気汚染データ
- Google Trends
- インサイダー取引（SEC Form 4）

### Tier 4: 週次
- 空売り残高（FINRA）
- 衛星画像分析
- 港湾コンテナ処理量
- 特許出願動向
- 議員取引（Capitol Trades）
- 13F Filing（四半期だが差分を週次チェック）

### Tier 5: イベントドリブン（発生時のみ）
- FOMC/日銀会合
- 決算発表
- 地政学的事件（戦争、制裁、首脳会談）
- 自然災害
- 規制発表
- 大型M&A/IPO

---

## 参考：関連OSSリポジトリ

| リポジトリ | 内容 |
|-----------|------|
| github.com/BigBodyCobain/Shadowbroker | 地政学OSINTダッシュボード |
| github.com/SC4RECOIN/FlowAlgo-Options-Trader | オプションフロー自動売買Bot |
| github.com/pmaji/crypto-whale-watching-app | 暗号クジラ監視ダッシュボード |
| github.com/Analitico-771/Crypto-Whale-Tracker | マルチアセットウォレット追跡 |
| github.com/factoredai/insiderTradingAPI_v1 | S&P500インサイダー取引データ+ML予測 |
| github.com/aluay/Insight | ダークプール+空売り+ニュース統合API |
| github.com/AISViz | AISデータ処理/可視化ツールボックス |
| github.com/SuperMayo/AIS_tracker | GitHub Actions定期船舶追跡 |
| github.com/followthemoney/vessel_research | 船舶調査ツール（Global Fishing Watch連携） |
| github.com/fitomad/App-Store-Ranking | App Store全国ランキング取得 |
| github.com/Quiver-Quantitative/python-api | Quiver Quant Python SDK（議員取引等） |
| github.com/QuantConnect/Lean.DataSource.QuiverQuantCongressTrading | 議員取引バックテスト統合 |
| github.com/topics/satellite-imagery-analysis | 衛星画像分析OSSコレクション |
| github.com/topics/options-trading | オプション取引関連OSS（362+リポジトリ） |
| github.com/topics/wallet-tracker | ウォレット追跡関連OSS |
