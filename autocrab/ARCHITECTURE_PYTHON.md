# AutoCrab (Python) Architecture Design

## 1. Executive Summary

This document defines the architecture for the Python port of the AutoCrab (formerly OpenClaw) agentic AI backend. The primary goals of this rewrite are to:

1.  **Resolve Critical Bottlenecks**: Eliminate the Node.js token-compaction memory flaw by introducing a robust Retrieval-Augmented Generation (RAG) semantic memory system.
2.  **Improve Reliability**: Replace fragile Node.js native bindings (`node-gyp`) with highly stable, pre-compiled Python wheels. Decouple the monolithic event loop to prevent channel webhook timeouts.
3.  **Maintain 100% Frontend Compatibility**: The Python backend must expose the exact same REST/WebSocket APIs as the original Gateway, ensuring the existing Lit Web UI and native iOS/macOS/Android apps continue to function without modification.
4.  **Embrace the Python AI Ecosystem**: Leverage industry-standard Python frameworks (FastAPI, LangGraph/LlamaIndex, Pydantic) to provide a superior developer experience for building agent skills and channel extensions.

---

## 2. Python Codebase Structure Diagram

```mermaid
graph TD
    User([User]) --> ClientApps
    User --> WebUI

    subgraph "Frontend Architecture (Unchanged)"
        ClientApps[Native Apps<br/>iOS/macOS Swift, Android Kotlin]
        WebUI[Web Control UI<br/>Vite + Lit Components]
    end

    subgraph Third-Party Integrations
        ExtChannels[Extensions / Channels<br/>Slack, Discord, Matrix]
    end

    User --> ExtChannels

    ClientApps <-->|WebSocket / REST| PyGateway
    WebUI <-->|WebSocket / REST| PyGateway
    ExtChannels <-->|Webhook / Async Task| MessageBroker

    subgraph "Python Backend Architecture (New)"
        PyGateway[FastAPI Gateway<br/>src/core/gateway]

        MessageBroker[[Redis/Celery Broker<br/>Async Task Queue]]
        MessageBroker --> PyGateway

        PyGateway <--> PluginSystem[Plugin SDK<br/>src/plugins (importlib)]

        PyGateway <--> AgentRuntime[LangGraph Agent Runtime<br/>src/core/agent]

        subgraph "Autonomous Engine (RAG Integration)"
            AgentRuntime --> ReAct[LangGraph ReAct Loop]
            ReAct --> RemoteRAG((External RAG System<br/>rag.test))
            ReAct --> SessionDB[(PostgreSQL / SQLite<br/>State & Config)]
        end

        AgentRuntime --> ToolSystem[Tool Sandbox<br/>src/tools (docker SDK)]
        AgentRuntime --> RemoteTools((External Tools<br/>mcp.test))
        AgentRuntime --> Skills[Python Skills<br/>src/skills]
        Skills --> MasterAgent((Master Agent Skill<br/>agent.test))
    end
```

---

## 3. Core System Components

### 3.1 The Gateway (`src/core/gateway/`)

- **Framework**: **FastAPI** coupled with `uvicorn` (ASGI). FastAPI provides native, high-performance async WebSocket support and auto-generated OpenAPI documentation.
- **Data Validation (`src/core/models/`)**: **Pydantic** replaces `zod`. Pydantic models will exactly mirror the original TypeScript interfaces, ensuring the API contract with the Swift/Kotlin/Web frontends remains unbroken.
- **Message Broker**: To fix the monolithic event loop drops, high-traffic channel webhooks (Discord/Slack) will push events to a message broker (e.g., Redis Queue or Celery) which the Gateway consumes asynchronously.

### 3.2 The Agent Runtime (`src/core/agent/`)

- **Framework**: **LangGraph** (or LlamaIndex workflows). Instead of a custom, highly complex `while` loop, LangGraph provides a robust, stateful abstraction for cyclical ReAct (Reason + Act) agent flows.
- **Subagents**: LangGraph's multi-agent capabilities will handle spawning background subagents.

### 3.3 Memory & State Preservation (RAG Integration)

### 3.3 Memory & State Preservation (Strict Backward Compatibility)

The Python port must operate **exactly like the original Node.js open-claw implementation by default**.

- **Session State**: **SQLAlchemy** (using SQLite) will manage basic configuration and user metadata.
- **Original Memory Strategy (Default)**: Out of the box, the Python backend must write the agent's logic, reasoning, and tool executions directly to local flat-file Markdown transcripts (`session-utils.fs`). When the session needs to summarize or load history, it reads directly from the filesystem exactly as the original `compaction.ts` did.
- **New Feature: External RAG Architecture (Opt-In Toggle)**:
  - To solve the historical context limits of the original implementation, the Python backend will introduce an external RAG integration (`rag.test`), but this feature will be **disabled by default**.
  - It is controlled by a strict feature flag: `ENABLE_EXTERNAL_RAG=true` alongside `RAG_SYSTEM_URL=http://rag.test`.
  - When toggled ON, writing to the Markdown transcript also pushes ingestion streams to the remote RAG system, and the ReAct Context loop retrieves from `rag.test/docs` instead of reading the filesystem transcripts back into memory.

### 3.4 Tool Execution & Remote Providers (`src/tools/`)

- **Local Containerization**: The original Docker CLI `setup-podman.sh` bash scripts are replaced with the official **Docker SDK for Python** (`docker-py`) to run `sandbox-common` commands.
- **Remote Tool Provider (MCP)**: AutoCrab will integrate with an external tools provider system (`mcp.test`) configured via environment variables (e.g., `MCP_PROVIDER_URL=http://mcp.test`). This provider serves live data tools (forex, stock, crypto, news) that the agent can dynamically invoke without executing local bash scripts.

### 3.5 Extension & Skill Ecosystem (`src/plugins/`)

- **Plugin Architecture**: Dynamic ESM `import()` crashes are resolved by using Python's standard `importlib` and decorator-based registries (e.g., `@autocrab.skill()`).
- **Master Agent Integration**: An external master agent system (`agent.test`) will be integrated strictly as an Extension/Skill, configured via environment variables (e.g., `MASTER_AGENT_URL=http://agent.test`). AutoCrab's core ReAct loop remains independent, but can delegate highly specialized, overarching requests to this master agent skill when necessary.
- **Community Parity**: The Python port natively supports Rich Messaging logic (Slack Block Kit, Discord UI threads) and CRON background jobs (via APScheduler or Celery Beat).
- **Native OS App Integrations**: The Python API Gateway must expose the exact same payload schemas so native Swift (iOS/macOS) and Kotlin (Android) apps can continue to leverage deep OS connections (Share Extensions, Home screen Widgets).
- **Media Understanding**: Multimodal ingestion pipelines (handling PDFs, images, audio) will be ported using Python-native libraries (e.g., `PyMuPDF`, `Pillow`).

### 3.6 CLI & Administration (`src/cli/`)

- **Framework**: **Typer** (built on Click) powers the `autocrab` administrative commands (`gateway`, `daemon`, `plugin install`).

### 3.7 Operational Scripts & Assets (`scripts/`, `assets/`, `docs/`)

- **Scripts Migration**: Existing Bash/TypeScript tooling for CI/CD, creating `.dmg` releases, and protocol generation will be gradually migrated to Python scripts (`src/scripts/`) or kept as Bash where appropriate.
- **Documentation**: The Mintlify-based documentation will be updated to reflect the new Python installation (Pip/Poetry) and architecture, replacing references to `pnpm` and `node`.

---

## 5. Testing & CI/CD Strategy

The Python backend must integrate seamlessly into the existing GitHub Actions matrix (`.github/workflows/ci.yml`).

- **Testing Framework**: **`pytest`** replaces `vitest`.
- **Test Scoping**: The test suite remains strictly partitioned into unit tests (`tests/unit`), gateway integration tests (`tests/integration/gateway`), and heavy Docker-based E2E tests (`tests/e2e`).
- **CI/CD Matrix Builds**: The GitHub Actions matrix must be updated to install Python 3.12 (using `actions/setup-python`) and `poetry`/`pip` instead of `pnpm`.
- **Frontend Build Protection**: **Crucially, the macOS Xcode 26.1 (Swift) and Ubuntu Gradle (Android) build jobs will remain completely untouched**. The Python PR must pass the exact same Swift/Kotlin tests to guarantee the frontend API contracts have not been violated.
- **Security**: Existing `detect-secrets` (generating `.secrets.baseline`) and `zizmor` pre-commit hooks will remain active to prevent API key leaks.

---

## 6. Recommended Phased Delivery Plan

A "big bang" rewrite of this monorepo is highly risky. The Python port must follow a strict, phased rollout strategy:

**Phase 1: API Gateway & Data Parity (The Skeleton)**

- Replicate the exact REST/WebSocket endpoints and Pydantic schemas corresponding to the original TS interfaces.
- **Verification**: The existing unmodified Lit Web UI and Swift macOS app must boot, authenticate, and connect to the Python backend without crashing.

**Phase 2: RAG Database & Prompt Engine (The Brain)**

- Build the LangGraph ReAct loops and the dual-write Markdown/RAG memory engine.
- **Verification**: Ensure the agent can maintain a conversational state and automatically fall back to standard Markdown files if the external `rag.test` is disabled.

**Phase 3: Core Tools & Sandboxing (The Hands)**

- Port the tool schemas (Bash, FS, Browser) using the Python Docker SDK.
- **Verification**: Run the existing `test-live-models-docker.sh` equivalent to ensure the LLM can execute a bash command inside the container and parse the `stdout`.

**Phase 4: Ecosystem & Plugins (The Community)**

- Establish the dynamic `importlib` plugin system for community skills.
- Integrate the external MCP Tools Provider (`mcp.test`) and the Master Agent extension (`agent.test`) behind feature flags.
- **Verification**: Launch the bot in a test Discord server and verify Rich Messaging (threads, cards) triggers seamlessly.

---

## 7. User Experience & Pain Points Resolution

As a project auditor, ensuring the new architecture actually solves historical user complaints (documented in `CHANGELOG.md` and `CONTRIBUTING.md`) is paramount. The Python port intrinsically resolves the top 4 structural pain points of the Node.js era:

### 7.1 Catastrophic API Costs & Context Memory Loss

- **The Historical Pain**: Users complained of massive frontier model API bills because the ReAct loop forcefully injected massive flat-file `tool_results` or dropped entire context blocks via the flawed `compaction.ts` algorithm.
- **The Python Resolution**: The **Hybrid Memory Strategy** (Section 3.3). By default, it operates identical to the original for basic tasks. But for heavy workflows, users can toggle `ENABLE_EXTERNAL_RAG`, allowing the agent to query `rag.test/docs` for exact semantic references instead of bloating the prompt window with raw files.

### 7.2 Fragile Installation & `node-gyp` Failures

- **The Historical Pain**: Community issues were flooded with installation errors on Windows and Linux related to complex native C++ bindings for Node (`canvas`, `sqlite3`, Opus Discord decoders) failing to compile via `node-gyp`.
- **The Python Resolution**: Python excels at distributing pre-compiled binary wheels via `pip`. Critical native libraries (like SQLAlchemy/SQLite, Pillow, PyMuPDF) will install seamlessly across all OS environments without requiring users to install C++ build tools.

### 7.3 Dropped Messages & Channel Reliability

- **The Historical Pain**: The monolithic Node.js event loop caused dropped Discord/Slack pings or duplicate replies when handling concurrent webhooks under heavy load.
- **The Python Resolution**: Decoupling the Gateway from the Agent Engine. High-traffic webhooks will be ingested instantly by FastAPI and shoved into a **Redis/Celery Message Broker**, guaranteeing 100% message delivery and allowing the Agent Engine to process threads asynchronously.

### 7.4 Plugin Authoring & "ESM Scope" Crashes

- **The Historical Pain**: Non-expert contributors struggled to build extensions because Node.js dynamic `import()` boundaries caused constant `require is not defined in ES module scope` runtime crashes.
- **The Python Resolution**: Python's `importlib` and `@autocrab.skill()` wrapper eliminates build-step bundling and strict module boundary crashes. Community users can simply drop a `.py` file into the plugins directory, and Python will reliably register the skill at runtime.
