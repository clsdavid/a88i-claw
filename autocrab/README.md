# AutoCrab — Python Gateway

<p align="center">
  <a href="https://github.com/clsdavid/autocrab/actions/workflows/ci.yml?branch=main"><img src="https://img.shields.io/github/actions/workflow/status/autocrab/autocrab/ci.yml?branch=main&style=for-the-badge" alt="CI status"></a>
  <a href="https://github.com/clsdavid/autocrab/releases"><img src="https://img.shields.io/github/v/release/autocrab/autocrab?include_prereleases&style=for-the-badge" alt="GitHub release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+">
</p>

**AutoCrab Python** is the Python port of the AutoCrab agentic AI backend.
It exposes the exact same WebSocket and REST APIs as the original Node.js gateway so the existing Web UI, macOS app, and iOS/Android nodes connect without modification.

[Architecture](ARCHITECTURE_PYTHON.md) · [Root repository](../README.md) · [Docs](https://docs.autocrab.ai) · [Discord](https://discord.gg/clawd)

---

## Why a Python Gateway?

| Pain point (Node.js era)                         | Python resolution                                                                      |
| ------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Context blowout from flat-file compaction        | Hybrid Memory: flat-file by default, optional External RAG (opt-in)                    |
| `node-gyp` C++ compile failures on Linux/Windows | Pre-compiled Python wheels — no build tools required                                   |
| Dropped messages under concurrent webhook load   | FastAPI + Celery/Redis message broker decouples ingestion from the agent loop          |
| ESM `require is not defined` plugin crashes      | `importlib`-based `@skill()` decorator — drop a `.py` file and it registers at runtime |

---

## Architecture at a glance

```
Web UI / macOS app / iOS / Android
            │
            ▼  WebSocket + REST
┌─────────────────────────────────────┐
│  FastAPI Gateway  (core/gateway)    │
│  uvicorn ASGI · port 5174           │
└────────────┬────────────────────────┘
             │
     ┌───────┴────────┐
     │                │
     ▼                ▼
LangGraph          Celery / Redis
ReAct Agent        (channel webhooks)
(core/agent)
     │
     ├─ Hybrid Memory (flat-file + opt-in RAG)
     ├─ Tool Sandbox  (Docker SDK)
     ├─ Plugin Skills (importlib)
     └─ MCP Remote Tools (opt-in)
```

Full details: [ARCHITECTURE_PYTHON.md](ARCHITECTURE_PYTHON.md)

---

## Requirements

- **Python 3.12+**
- **Docker** (for the tool sandbox; optional for gateway-only use)
- **Redis** (for Celery; only required when using channel webhook ingestion)

---

## Quick start

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install in editable mode with dev extras
pip install -e ".[dev]"

# 3. (Optional) copy and edit the sample config
cp config/autocrab.sample.json ~/.autocrab_v2/autocrab.json

# 4. Start the gateway
PYTHONPATH=src python3 -m autocrab.core.gateway.main
# Gateway is now running at http://localhost:5174
```

The Web UI is served automatically from `frontend/dist/` when present.
Open `http://localhost:5174` in your browser.

---

## Configuration

The gateway loads config from `~/.autocrab_v2/autocrab.json` (JSON5 supported).
Override the location with `AUTOCRAB_HOME=/path/to/dir` or `AUTOCRAB_CONFIG_PATH=/path/to/file`.

Minimal example connecting to a local Ollama instance:

```json5
{
  gateway: { port: 5174, mode: "local" },
  models: {
    providers: {
      ollama: {
        baseUrl: "http://localhost:11434",
        models: [{ id: "ollama/qwen2.5:72b", name: "qwen2.5:72b" }],
      },
    },
  },
  agents: {
    defaults: { model: { primary: "ollama/qwen2.5:72b" } },
    list: [{ id: "main", name: "AutoCrab", default: true }],
  },
}
```

All configuration keys and their types are exposed as a live JSON Schema via the
`config.schema` WebSocket method (backed by `AutoCrabSettings.model_json_schema()`).

### Environment variables

| Variable                | Default          | Description                      |
| ----------------------- | ---------------- | -------------------------------- |
| `AUTOCRAB_HOME`         | `~/.autocrab_v2` | Config + session root directory  |
| `AUTOCRAB_CONFIG_PATH`  | _(unset)_        | Override path to `autocrab.json` |
| `AUTOCRAB_GATEWAY_PORT` | `5174`           | Gateway listen port              |
| `ENABLE_EXTERNAL_RAG`   | `false`          | Enable opt-in Remote RAG system  |
| `RAG_SYSTEM_URL`        | _(unset)_        | URL of the external RAG service  |
| `ENABLE_EXTERNAL_MCP`   | `false`          | Enable opt-in MCP remote tools   |
| `MCP_PROVIDER_URL`      | _(unset)_        | URL of the MCP tool provider     |
| `MASTER_AGENT_URL`      | _(unset)_        | URL of the master agent delegate |

---

## CLI

The `autocrab` CLI is powered by **Typer**.

```bash
# Show available commands
autocrab --help

# Start the gateway (foreground)
autocrab gateway run

# Start as a background daemon
autocrab gateway run --daemonize

# Check channel status
autocrab channels status
```

---

## Project layout

```
autocrab/
├── src/
│   └── autocrab/
│       ├── cli/              # Typer CLI (autocrab gateway / channels / …)
│       ├── core/
│       │   ├── agent/        # LangGraph ReAct loop + Hybrid Memory
│       │   ├── gateway/      # FastAPI app, WebSocket handler, REST routes
│       │   ├── models/       # Pydantic schemas (config, gateway protocol)
│       │   ├── plugins/      # importlib skill loader + @skill() decorator
│       │   ├── routing/      # Channel → agent routing engine
│       │   ├── sandbox/      # Docker SDK tool sandbox manager
│       │   ├── tools/        # Bash, FS, browser, MCP tool specs
│       │   └── webhooks/     # Celery app + channel webhook consumers
│       └── plugins/
│           └── channels/     # Built-in channel plugins
│               ├── discord/
│               ├── telegram/
│               ├── slack/
│               ├── signal/
│               ├── whatsapp/
│               ├── imessage/
│               └── web/
├── tests/
│   ├── unit/                 # Fast, isolated unit tests (pytest)
│   └── integration/          # Gateway integration tests (httpx + ASGI)
├── config/                   # Sample configuration files
├── pyproject.toml
└── requirements-dev.txt
```

---

## Gateway WebSocket protocol

The Python gateway implements the same WebSocket handshake as the original Node.js gateway:

```
Client → connect          (challenge)
Server → hello-ok         (features, snapshot, policy)
Server → connect.ack      (connId, snapshot)
Client → req              (id, method, params)
Server → response         (id, ok, payload | error)
Server → event            (type, event, payload)
```

### Implemented RPC methods

| Category     | Methods                                                                                                                    |
| ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Chat**     | `chat.send`, `chat.history`                                                                                                |
| **Config**   | `config.get`, `config.set`, `config.apply`, `config.schema`                                                                |
| **Sessions** | `sessions.list`, `sessions.delete`, `sessions.patch`, `sessions.usage`, `sessions.usage.logs`, `sessions.usage.timeseries` |
| **Agents**   | `agents.list`, `agent.identity.get`, `agents.files.list`, `agents.files.get`, `agents.files.set`                           |
| **Channels** | `channels.status`, `channels.logout`                                                                                       |
| **Models**   | `models.list`                                                                                                              |
| **Skills**   | `skills.status`, `skills.bins`, `skills.install`, `skills.update`                                                          |
| **Cron**     | `cron.runs`, `cron.list`, `cron.status`, `cron.add`, `cron.remove`, `cron.run`, `cron.update`                              |
| **Tools**    | `tools.catalog`, `exec.approvals.get`, `exec.approvals.set`                                                                |
| **Logs**     | `logs.tail`                                                                                                                |
| **Device**   | `device.pair.approve`, `device.pair.reject`, `device.token.revoke`                                                         |
| **Nodes**    | `node.list`                                                                                                                |
| **System**   | `status`, `health`, `last-heartbeat`, `ping`, `system-presence`, `system-event`                                            |
| **Misc**     | `update.run`, `usage.cost`, `whatsapp`                                                                                     |

---

## Development

### Install dev dependencies

```bash
pip install -e ".[dev]"
# or
pip install -r requirements-dev.txt
```

### Run tests

```bash
pytest                        # all tests
pytest tests/unit/            # unit tests only
pytest tests/integration/     # integration tests only
pytest -x -q                  # fail-fast, quiet output
```

### Lint and type-check

```bash
ruff check src/ tests/        # lint
ruff format src/ tests/       # format
mypy src/                     # type check
```

### Start the gateway in watch mode (auto-reload)

```bash
PYTHONPATH=src uvicorn autocrab.core.gateway.main:app --reload --port 5174
```

---

## Feature flags

All non-default integrations are gated behind explicit environment flags to keep the
baseline footprint small and the startup time fast.

| Flag                                            | Enables                                                                                          |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `ENABLE_EXTERNAL_RAG=true` + `RAG_SYSTEM_URL`   | Opt-in Hybrid RAG — semantic memory via remote RAG service instead of flat-file transcript scans |
| `ENABLE_EXTERNAL_MCP=true` + `MCP_PROVIDER_URL` | MCP remote tool registry (live data: forex, stock, crypto, news)                                 |
| `MASTER_AGENT_URL`                              | Master Agent delegation skill — escalates to an external master agent for specialised tasks      |

---

## Channel plugins

Built-in channel plugins live under `src/autocrab/plugins/channels/`.
Each plugin implements a standard interface (`start`, `stop`, optional `handle_rpc`)
and is auto-discovered at gateway startup via `importlib`.

| Channel  | Status                  |
| -------- | ----------------------- |
| Discord  | Active (discord.py bot) |
| Telegram | Stub (token required)   |
| Slack    | Stub                    |
| Signal   | Stub                    |
| WhatsApp | Stub                    |
| iMessage | Stub                    |
| Web      | Stub                    |

Community plugins follow the same pattern — drop a directory with a `plugin.py` that
calls `register_channel_plugin(name, plugin_instance)` and the gateway picks it up automatically.

---

## Key dependencies

| Package                          | Role                                      |
| -------------------------------- | ----------------------------------------- |
| `fastapi` + `uvicorn`            | ASGI gateway + WebSocket server           |
| `pydantic` + `pydantic-settings` | Schema validation + settings management   |
| `langgraph` + `langchain-openai` | ReAct agent loop + LLM bindings           |
| `sqlalchemy`                     | Session/config state (SQLite by default)  |
| `docker`                         | Tool sandbox (Docker SDK for Python)      |
| `celery` + `redis`               | Async message broker for channel webhooks |
| `typer`                          | CLI framework                             |
| `json5`                          | JSON5 config file parsing                 |

---

## License

MIT — see [LICENSE](../LICENSE).
