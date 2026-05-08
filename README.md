# Kane — Realtime EN ⇄ JA Translator (Beta)

スマホブラウザから利用できる、英語⇄日本語のリアルタイム同時通訳ベータ版です。
OpenAI の **Realtime 2** モデル (`gpt-realtime-2`) を WebRTC 経由で利用します。

- 🎙 マイク入力をそのままモデルへストリーミング（低レイテンシ）
- 🗣 検知した言語を自動でもう一方に通訳した音声を再生
- 📝 オプションでリアルタイム字幕を表示
- 📱 iPhone / Android のブラウザを想定したダーク UI

ベータ版なのでデザインも機能も最小限に絞ってあります。話者が交互に英語/日本語で
話すだけで、Kane が自動で逆方向に通訳して読み上げます。

---

## アーキテクチャ

```
[スマホブラウザ]
    │  1) POST /api/session (voice の希望のみ)
    ▼
[FastAPI サーバ] ──2) POST /v1/realtime/client_secrets──▶ [OpenAI]
    │  3) ek_... を返す
    ▼
[スマホブラウザ] ──4) WebRTC SDP を /v1/realtime/calls へ──▶ [OpenAI Realtime 2]
                  ▲ 5) DataChannel で session.update（通訳プロンプト）
                  └─ 6) 音声が ontrack で双方向に流れる
```

API キーはサーバ側でしか扱わず、ブラウザは短命の ephemeral key (`ek_...`) のみを
受け取ります。

---

## セットアップ

### 1. 依存をインストール

Python 3.11 以上。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 環境変数を設定

```bash
cp .env.example .env
# .env を編集して OPENAI_API_KEY を入れる
```

### 3. 起動

```bash
kane
# もしくは
python -m kane.server
# もしくは
uvicorn kane.server:app --host 0.0.0.0 --port 8000
```

PC からは <http://localhost:8000> でアクセスできます。

---

## スマホで試す（ローカル開発）

WebRTC とマイクアクセスは **HTTPS（または `localhost`）** が必須です。PC で開発中に
スマホから試すには以下のいずれかで HTTPS 終端を用意してください。

### 例: Cloudflare Tunnel（無料・推奨）

```bash
cloudflared tunnel --url http://localhost:8000
# 表示された https://xxxx.trycloudflare.com をスマホで開く
```

### 例: ngrok

```bash
ngrok http 8000
# 表示された https://xxxx.ngrok.app をスマホで開く
```

スマホ側でマイクの許可を出して `START` を押せば通訳が始まります。`STOP` でセッション
終了。設定 (⚙) から音声 (`marin` / `cedar` など) と字幕の有無を変更できます。

---

## VPS に常駐させる（Docker + Caddy）

PC を起動し続けないために、Docker compose で **アプリ + Caddy リバースプロキシ**を
立てて自動 HTTPS にする構成です。

### 前提

- VPS で 80 / 443 / 22 が空いていて、Docker と Docker Compose がインストール済み
- 公開できるホスト名がある。**ドメインがなくても OK**：
  - 一番楽: [DuckDNS](https://www.duckdns.org/) で無料サブドメインを取得し、A レコードを VPS の IP に設定
  - もっと楽: `sslip.io` を使う。VPS の IP が `203.0.113.9` なら `203-0-113-9.sslip.io` がそのまま使える

### 1. ファイルを VPS に置く

```bash
ssh user@your-vps
git clone https://github.com/jtakuya3/kane.git
cd kane
git checkout claude/realtime-translation-app-1KZlX
```

### 2. `.env` を作る

```bash
cp .env.example .env
nano .env
```

最低限これらを埋めます：

```env
OPENAI_API_KEY=sk-...
KANE_ACCESS_TOKEN=$(openssl rand -hex 24 を入れる)
KANE_HOST=kane-yours.duckdns.org   # または 203-0-113-9.sslip.io
LETSENCRYPT_EMAIL=you@example.com
```

### 3. 起動

```bash
docker compose up -d --build
docker compose logs -f caddy   # 証明書取得を確認
```

Caddy が Let's Encrypt 証明書を自動取得します。`https://<KANE_HOST>` をスマホで開
くと、最初にパスワード（`KANE_ACCESS_TOKEN`）の入力を求められます。

### 4. アップデート / 再起動

```bash
git pull
docker compose up -d --build
```

### トラブルシュート

- 証明書が取れない: `KANE_HOST` の DNS が VPS の IP に向いているか / 80・443 ポート
  がファイアウォールで開いているか確認。`docker compose logs caddy` を見る。
- スマホからマイクが動かない: ブラウザの URL バーに鍵マーク (HTTPS) が出ているか。
- 401 が返る: ブラウザの「合言葉」入力でタイポしていないか、`KANE_ACCESS_TOKEN` が
  サーバ側と一致しているか。

### セキュリティのポイント

- `KANE_ACCESS_TOKEN` はブラウザの localStorage に保存されます。物理的にスマホを
  触れる人はアクセスできるので、共有用途なら定期的にトークンをローテートしてください。
- API レートリミットは未実装。気になる場合は Caddy で `rate_limit` プラグインを
  足すか、OpenAI 側の使用量上限を設定するのが手っ取り早いです。

---

## 使い方のコツ

- 静かな環境で、話したいフレーズが終わったら 0.5〜1 秒の間を空けるとモデルが
  ターンを認識して通訳音声を返します（サーバ VAD）。
- 話し終わる前に通訳が走ってしまう場合は、`app.js` の `silence_duration_ms` を
  大きめに調整してください（既定 600ms）。
- 二人で会話する場合は同じスマホをマイク代わりにテーブル中央に置き、それぞれが
  自分の言語で話せばリアルタイムに通訳されます。

---

## ファイル構成

```
kane/
  server.py          FastAPI: ephemeral key の発行 + 静的ファイル配信
  static/
    index.html       SPA
    styles.css       モバイルファーストのダーク UI
    app.js           WebRTC 接続 + 通訳プロンプト + 字幕レンダリング
pyproject.toml       FastAPI / uvicorn / httpx / dotenv 依存
.env.example         API キーやモデル名のテンプレ
```

---

## 注意

- これはベータ版・プロトタイプです。エラー処理・再接続・ロールはまだ最小限。
- Realtime 2 はストリーミング課金です。長時間放置しないように `STOP` を忘れずに。
- ephemeral key は数分で失効しますが、外部に流出しないようにしてください。
