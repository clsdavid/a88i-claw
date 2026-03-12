# Python Backend Architecture & Migration Plan

## Goal

Replace the Node.js/TypeScript backend (`src/`) with a feature-complete Python implementation (`python-backend/`) while maintaining full compatibility with the AutoCrab UI and CLI.

## Current State vs Target State

| Feature Area | Node.js Implementation (`src/`)      | Current Python Backend   | Target Python Implementation           |
| ------------ | ------------------------------------ | ------------------------ | -------------------------------------- |
| **Server**   | `src/gateway/server.ts` (Fastify/WS) | `main.py` (FastAPI/WS)   | `src/gateway/server.py`                |
| **Methods**  | `src/gateway/server-methods/*.ts`    | All in `main.py`         | `src/gateway/methods/*.py`             |
| **Config**   | `src/config/*.ts` (Zod schemas)      | `config.py` (Pydantic)   | `src/config/` (Pydantic + JSON Schema) |
| **Agents**   | `src/agents/`                        | Minimal mock             | `src/agents/` (Full agent logic)       |
| **Channels** | `src/channels/` (Discord/Slack/etc)  | None                     | `src/channels/` (Plugin system)        |
| **Database** | n/a (File system)                    | File system (`aiofiles`) | File system (Compatible structure)     |

## Proposed Directory Structure

```
python-backend/
├── main.py                 # Entry point (FastAPI app)
├── config.json             # Backend configuration
├── requirements.txt        # Dependencies
├── src/
│   ├── gateway/
│   │   ├── server.py       # WebSocket connection manager
│   │   └── methods/        # Individual RPC method handlers
│   │       ├── base.py     # Base handler class
│   │       ├── config.py   # config.get, config.set, config.schema
│   │       ├── chat.py     # chat.history, chat.send
│   │       ├── agents.py   # agents.list, agent.identity.get
│   │       ├── tools.py    # tools.catalog
│   │       ├── nodes.py    # node.list
│   │       └── ...
│   ├── config/
│   │   ├── manager.py      # Config loading/saving
│   │   └── schema.py       # Schema generation (Pydantic -> JSON Schema)
│   ├── agents/
│   │   ├── runtime.py      # Agent execution runtime
│   │   └── registry.py     # Agent discovery
│   ├── models/
│   │   └── client.py       # LLM Client (Ollama, OpenAI, etc.)
│   └── utils/
│       └── filesystem.py   # Async file operations
```

## Missing Features to Implement

Based on `src/gateway/server-methods/`, the following features need implementation:

1.  **Full Configuration Management**:
    - [x] `config.get` (Stubbed)
    - [x] `config.schema` (Stubbed)
    - [ ] `config.set` (Write support)
    - [ ] `config.schema.lookup` (Full implementation)

2.  **Agent System**:
    - [x] `agents.list` (Stubbed)
    - [x] `agent.identity.get` (Stubbed)
    - [ ] `agent.status`
    - [ ] Agent runtime for tool execution

3.  **Channel Integrations**:
    - [ ] `channels.list`
    - [ ] `channels.status`
    - [ ] Webhook endpoints for external providers

4.  **System/Doctor**:
    - [x] `health`
    - [x] `doctor.memory.status`
    - [ ] `logs.tail`
    - [ ] `usage.get`

## Separation Strategy

1.  **Modularization**: Move logic out of `main.py` into `src/` modules immediately.
2.  **Schema Parity**: Use Pydantic models to define the exact configuration structure expected by the UI, generating JSON schemas dynamically to satisfy `config.schema`.
3.  **Protocol Compliance**: Ensure all RPC methods in `src/gateway/server-methods-list.ts` are at least stubbed in Python to prevent UI errors.

## Next Steps

1.  Refactor `main.py` to use a router/dispatcher pattern for WebSocket methods.
2.  Implement `config.schema` properly using Pydantic's `model_json_schema()`.
3.  Flesh out `agents.list` to actually scan for agents.
