# Kane

Your personal AI assistant. Inspired by [OpenClaw](https://github.com/openclaw/openclaw).

Kane is a Python-based personal AI assistant system that runs locally and integrates with LLMs to provide an extensible, multi-channel AI agent platform.

## Architecture

```
kane/
├── gateway/        # Central control plane (server, session, router)
├── channels/       # Messaging integrations (CLI, Webhook)
├── agents/         # AI agent system with LLM integration
├── skills/         # Plugin system with built-in skills
│   └── builtin/    # Shell, WebSearch, FileManager
├── memory/         # Persistent storage and conversation history
├── config/         # Settings management
└── cli.py          # CLI entry point
```

### Key Components

- **Gateway** - Hub-and-spoke control plane that connects channels, agents, and skills
- **Channels** - Multi-channel messaging (CLI terminal, HTTP Webhook)
- **Agents** - LLM-powered agents with tool-calling loop (OpenAI & Anthropic compatible)
- **Skills** - Extensible plugin system with built-in shell, web search, and file management
- **Memory** - Persistent key-value store and per-session conversation history
- **Multi-Agent Routing** - Route messages to different agents based on channel/sender rules

## Features

- Model-agnostic: supports OpenAI, Anthropic, and any OpenAI-compatible API
- Multi-channel: CLI and Webhook channels (extensible)
- Plugin system: easily add new skills
- Local-first: all data stored on your machine
- Agent loop: automatic tool-calling with LLM
- Session management: persistent conversations with timeout

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

3. Run the onboarding wizard
```bash
kane onboard
```

4. Start the assistant
```bash
kane start
```

### Development Commands
- Run tests: `poetry run pytest`
- Run linting: `poetry run flake8`
- Format code: `poetry run black .`

## Usage

### Quick Start (CLI mode)
```bash
# Configure your LLM API key
kane onboard

# Start the assistant
kane start
```

### Webhook Mode
```bash
# Start with both CLI and webhook channels
kane start --channel cli webhook

# Send a message via HTTP
curl -X POST http://localhost:8322/message \
  -H "Content-Type: application/json" \
  -d '{"sender": "user1", "content": "Hello Kane!"}'
```

### Configuration
Configuration is stored at `~/.kane/config.json`:
```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": "your-key"
  },
  "gateway": {
    "host": "127.0.0.1",
    "port": 8321
  },
  "enabled_channels": ["cli"],
  "enabled_skills": ["shell", "web_search", "file_manager"]
}
```

## License

MIT
