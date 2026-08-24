# Kane

A Python package for [description to be added].

## OXalpha チャット (OpenRouter)

OpenRouter 経由で OXalpha モデルとチャットできる CLI です（追加の依存ライブラリ不要）。

1. APIキーを設定（`.env` は gitignore 済みなのでコミットされません）

```bash
cp .env.example .env
# .env を開いて OPENROUTER_API_KEY に自分のキーを設定
```

2. チャット開始

```bash
python -m kane.oxalpha_chat
# または poetry install 済みなら
poetry run oxalpha-chat
```

起動時に "oxalpha" に一致するモデルIDを自動検出します。見つからない場合や別モデルを使う場合:

```bash
python -m kane.oxalpha_chat --list-models alpha   # モデルIDを検索
python -m kane.oxalpha_chat --model <正確なモデルID>
```

チャット中のコマンド: `/exit` で終了、`/clear` で履歴クリア。`--system "..."` でシステムプロンプト指定。

## Development Setup

### Prerequisites
- Python 3.12 (managed via pyenv)
- pip/poetry for package management

### Setup Instructions
1. Clone the repository
```bash
gh repo clone jtakuya3/kane
cd kane
```

2. Set up Python environment
```bash
poetry install
```

3. Run tests
```bash
poetry run pytest
```

### Development Commands
- Run tests: `poetry run pytest`
- Run linting: `poetry run flake8`
- Format code: `poetry run black .`
