"""Interactive chat CLI for the OXalpha model on OpenRouter.

Usage:
    export OPENROUTER_API_KEY=sk-or-v1-...   # or put it in .env
    python -m kane.oxalpha_chat              # start chatting
    python -m kane.oxalpha_chat --list-models oxalpha

Uses only the Python standard library (no extra dependencies).
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL_QUERY = "oxalpha"


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (no overwrite)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        sys.exit(
            "OPENROUTER_API_KEY が設定されていません。\n"
            "  .env ファイルに OPENROUTER_API_KEY=sk-or-v1-... と書くか、\n"
            "  export OPENROUTER_API_KEY=sk-or-v1-... を実行してください。"
        )
    return key


def _request(url: str, api_key: str, payload: dict | None = None) -> urllib.request.Request:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # Optional attribution headers recommended by OpenRouter
        "HTTP-Referer": "https://github.com/jtakuya3/kane",
        "X-Title": "kane oxalpha chat",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    return urllib.request.Request(url, data=data, headers=headers)


def fetch_models(api_key: str) -> list[dict]:
    req = _request(f"{API_BASE}/models", api_key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("data", [])


def _normalize(s: str) -> str:
    return re.sub(r"[-_./\s]", "", s.lower())


def resolve_model(api_key: str, query: str) -> str:
    """Find the exact OpenRouter model id matching a fuzzy name like 'OXalpha'."""
    norm_query = _normalize(query)
    models = fetch_models(api_key)
    matches = [
        m["id"]
        for m in models
        if norm_query in _normalize(m.get("id", "")) or norm_query in _normalize(m.get("name", ""))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        sys.exit(
            f"'{query}' に一致するモデルが見つかりませんでした。\n"
            "  --list-models <キーワード> で検索するか、--model で正確なIDを指定してください。"
        )
    print(f"'{query}' に複数のモデルが一致しました:", file=sys.stderr)
    for mid in matches:
        print(f"  {mid}", file=sys.stderr)
    sys.exit("--model オプションで正確なIDを指定してください。")


def list_models(api_key: str, query: str) -> None:
    norm_query = _normalize(query)
    for m in fetch_models(api_key):
        if norm_query in _normalize(m.get("id", "")) or norm_query in _normalize(m.get("name", "")):
            print(f"{m['id']}\t{m.get('name', '')}")


def stream_chat(api_key: str, model: str, messages: list[dict]) -> str:
    """Send a chat completion request and stream the reply to stdout."""
    payload = {"model": model, "messages": messages, "stream": True}
    req = _request(f"{API_BASE}/chat/completions", api_key, payload)
    reply_parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"].get("message", str(chunk["error"])))
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    reply_parts.append(content)
                    print(content, end="", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    print()
    return "".join(reply_parts)


def repl(api_key: str, model: str, system_prompt: str | None) -> None:
    print(f"モデル: {model}")
    print("チャットを開始します。終了は /exit、履歴クリアは /clear。\n")
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    while True:
        try:
            user_input = input("あなた> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            break
        if user_input == "/clear":
            messages = messages[:1] if system_prompt else []
            print("履歴をクリアしました。\n")
            continue
        messages.append({"role": "user", "content": user_input})
        print(f"{model.split('/')[-1]}> ", end="", flush=True)
        try:
            reply = stream_chat(api_key, model, messages)
        except (RuntimeError, urllib.error.URLError, TimeoutError) as e:
            print(f"\nエラー: {e}", file=sys.stderr)
            messages.pop()  # keep history consistent with what the model saw
            continue
        messages.append({"role": "assistant", "content": reply})
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with OXalpha via OpenRouter")
    parser.add_argument(
        "--model",
        default=os.environ.get("OXALPHA_MODEL", ""),
        help="OpenRouter model id (default: auto-resolve a model matching 'oxalpha')",
    )
    parser.add_argument("--system", default=None, help="system prompt")
    parser.add_argument(
        "--list-models",
        metavar="QUERY",
        default=None,
        help="search available model ids by keyword and exit",
    )
    args = parser.parse_args()

    load_dotenv()
    api_key = get_api_key()

    if args.list_models is not None:
        list_models(api_key, args.list_models)
        return

    model = args.model or resolve_model(api_key, DEFAULT_MODEL_QUERY)
    repl(api_key, model, args.system)


if __name__ == "__main__":
    main()
