# Kane LMS

研修動画をアップロードし、**共有リンク**でクライアントに視聴してもらえる、シンプルな
LMS（Learning Management System）です。Flask 製で、データベースは SQLite、動画は
ローカルディスクに保存します。外部サービス不要で、すぐに動かせます。

## 主な機能

- 🔐 **管理者ログイン**（パスワード1つだけのシンプル認証）
- 📚 **研修コース**の作成・削除
- 🎬 **動画アップロード**（mp4 / webm / mov / m4v / ogg）
- 🔗 **共有リンクの発行** — クライアントはログイン不要でリンクから視聴
  - クライアント名のメモ、有効期限（日数）の設定が可能
- ▶️ **プレイリスト付き視聴ページ** — シーク（Range リクエスト）対応のストリーミング

## セットアップ

### 前提
- Python 3.12（pyenv 推奨。3.11 でも動作します）
- poetry もしくは pip

### インストール

poetry を使う場合:

```bash
poetry install
```

pip を使う場合:

```bash
pip install flask
```

## 起動方法

```bash
# 管理者パスワードを設定（未設定だと既定値 "admin"）
export KANE_ADMIN_PASSWORD="あなたのパスワード"
export KANE_SECRET_KEY="ランダムな長い文字列"

# 開発サーバーを起動
flask --app kane.app run
# もしくは
python -m kane.app
```

ブラウザで <http://127.0.0.1:5000/> を開き、設定したパスワードでログインします。

### 使い方の流れ

1. ログイン後、ダッシュボードで **コースを作成**
2. コース詳細ページで **研修動画をアップロード**
3. **共有リンクを発行**し、URL をクライアントに送付
4. クライアントはリンクを開くだけで（ログイン不要で）動画を視聴できます

## 設定（環境変数）

| 変数名 | 既定値 | 説明 |
| --- | --- | --- |
| `KANE_ADMIN_PASSWORD` | `admin` | 管理画面のログインパスワード |
| `KANE_SECRET_KEY` | 起動毎にランダム | セッション署名鍵（本番では必ず固定値を設定） |
| `KANE_DB_PATH` | `instance/kane.db` | SQLite ファイルのパス |
| `KANE_UPLOAD_DIR` | `instance/uploads` | 動画の保存先ディレクトリ |
| `KANE_MAX_UPLOAD_MB` | `2048` | 1ファイルの最大アップロードサイズ(MB) |
| `KANE_HOST` / `KANE_PORT` | `127.0.0.1` / `5000` | `python -m kane.app` 起動時のホスト/ポート |

> アップロードされた動画と SQLite DB は `instance/` 配下に保存され、Git 管理対象外です。

## 開発コマンド

- テスト実行: `poetry run pytest`（または `python -m pytest`）
- Lint: `poetry run flake8`
- フォーマット: `poetry run black .`

## 本番運用のヒント

- `KANE_SECRET_KEY` と `KANE_ADMIN_PASSWORD` は必ず強固な値を設定してください。
- 開発サーバーではなく Gunicorn 等を使うことを推奨します:
  ```bash
  gunicorn "kane.app:app"
  ```
- 大容量動画を扱う場合は、リバースプロキシ（Nginx 等）側のアップロード上限も
  併せて調整してください。
