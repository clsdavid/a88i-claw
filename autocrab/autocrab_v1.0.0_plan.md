# AutoCrab v1.0.0 Delivery Plan (Python Migration)

This document serves as the formal Project Delivery Plan for migrating the AutoCrab AI Agent backend from Node.js to Python. It outlines the technology stack, phased implementation milestones, and risk mitigation strategies to ensure a zero-breakage transition for existing frontends. All new backend code will be strictly contained within the `autocrab/` directory.

## 1. Approved Technology Stack

- **Language**: Python 3.12+
- **Core Framework**: FastAPI, Uvicorn, Pydantic (replacing Zod)
- **Agent Orchestration**: LangGraph
- **Database & State**: SQLAlchemy, SQLite (local) / PostgreSQL (enterprise)
- **Container Sandbox**: Docker SDK for Python
- **Message Broker**: Redis, Celery (replacing monolithic event loop)
- **Package Management**: Pip with `requirements.txt` (or Poetry)
- **Testing & QA**: `pytest`, `ruff`, `mypy`

## 2. Phased Implementation Milestones

### Phase 1: API Gateway & Data Parity (The Skeleton)

**Goal**: Establish the core HTTP/WebSocket server and replicate exact TypeScript data models inside `autocrab/`.

- **Deliverables**:
  - `autocrab/src/core/models/`: Pydantic `BaseSettings` and `BaseModel` classes matching Swift/Kotlin expectations.
  - `autocrab/src/core/gateway/`: FastAPI HTTP/WebSocket routes, auth middleware, stubbed Agent endpoints.
  - `autocrab/src/cli/`: Typer-based CLI for `autocrab start`.
- **Validation**: Existing Lit Web UI and Swift macOS app must boot, authenticate, and connect without crashing. Swift unit tests must pass. All paths are relative to `autocrab/`.

### Phase 2: Hybrid Memory & Prompt Engine (The Brain)

**Goal**: Replace Node.js Compaction with Dual-Write FS + External RAG memory, and build the ReAct flow within `autocrab/`.

- **Deliverables**:
  - **State Management**: SQLAlchemy models for Users, Sessions, and Channels within `autocrab/src/core/db/`.
  - **Hybrid Memory**: Markdown Transcript Writer (default FS behavior) + RAG Ingestion Hook behind `ENABLE_EXTERNAL_RAG=true`.
  - **Agent Runtime**: LangGraph ReAct cyclic graph (Build Context -> Query LLM -> Parse -> Execute) located at `autocrab/src/core/agent/`.
- **Validation**: The agent maintains conversational state, defaulting to local Markdown writes, and successfully falls back from/to `rag.test` when toggled.

### Phase 3: Core Tools & Secure Sandboxing (The Hands)

**Goal**: Port system tools and securely execute them in isolated containers.

- **Deliverables**:
  - **Docker Orchestration** (`autocrab/src/tools/sandbox/`): Python Docker SDK integration replacing Bash spawn scripts.
  - **Tool Implementation**: Port core `bash`, `fs`, and `browser` tools as local defaults to `autocrab/src/tools/`.
  - **Remote MCP Registry**: Integrate `mcp.test` behind `ENABLE_EXTERNAL_MCP=true` to dynamically fetch live tool schemas.
- **Validation**: Python successfully builds a sandbox container, runs a tool constraint check via `pytest autocrab/tests/integration/docker/`, and tears it down cleanly.

### Phase 4: Ecosystem, Plugins & Master Agent (The Community)

**Goal**: Restore community features, webhook reliability, and third-party skills inside `autocrab/`.

- **Deliverables**:
  - **Async Channels**: Redis/Celery background queue for high-volume Discord/Slack webhooks.
  - **Plugin System** (`autocrab/src/plugins/`): `importlib` based loader and `@autocrab.skill()` decorators.
  - **Master Agent Integration**: Explicit skill to interface with `agent.test` via `MASTER_AGENT_URL`.
- **Validation**: End-to-end stack test via UI. Agent executes a complex request across native tools and remote integrations without event loop drops.

## 3. Risk Management & Mitigation

| Risk Area                | Potential Impact                                                    | Mitigation Strategy                                                                                                                                 |
| :----------------------- | :------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codebase Isolation**   | Original Node.js base is polluted.                                  | **Strict Working Directory**: All development is confined exclusively to the `autocrab/` subdirectory.                                              |
| **Frontend Breakage**    | iOS/Android native apps crash due to JSON casing or missing fields. | **Strict CI/CD**: Do not alter the macOS Xcode or Ubuntu Gradle test jobs. Python PRs must pass the raw Swift/Kotlin unit tests.                    |
| **API Cost Blowout**     | New runtime injects massive tool logs into the context window.      | **Feature Flag RAG**: Default to flat-file but encourage enterprise users to enable `ENABLE_EXTERNAL_RAG` to semantically chunk logs.               |
| **Sandbox Escapes**      | Python Docker SDK implementation incorrectly mounts host volumes.   | **E2E Testing**: Maintain the existing `test-live-models-docker.sh` equivalent tests to run malicious breakouts in CI. Retain `zizmor`.             |
| **Plugin Compatibility** | Contributors struggle to port legacy ESM Node plugins to Python.    | **Clear Porting Guide**: Document exactly how to write an `@autocrab.skill()`. The `importlib` approach is inherently simpler, minimizing friction. |

---

**Status**: Approved for Implementation.
