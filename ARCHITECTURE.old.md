# AutoCrab Architecture

**Original Source:** Forked from OpenClaw 3.3.
**Maintainer:** Dr Leshi Chen <chenleshi@hotmail.com>
**License:** MIT (See [LICENSE](LICENSE))

---

## 1. System Overview

AutoCrab is a personal AI assistant platform designed for self-hosting, privacy, and extensibility. It acts as a central gateway between Large Language Models (LLMs) and your digital life (messaging channels, local devices, web services).

### High-Level Data Flow

```mermaid
graph TD
    User[User / Client App] -->|Message/Action| Channel[Channel Extension]
    Channel -->|Unified Protocol| Gateway[AutoCrab Gateway]
    Gateway -->|Auth & Routing| Agent[AI Agent]
    Agent -->|Inference| LLM[LLM Provider (OpenAI/Anthropic/Ollama)]
    Agent -->|Tool Execution| Tool[Tools / Skills]
    Tool -->|Result| Agent
    Agent -->|Response| Gateway
    Gateway -->|Unified Protocol| Channel
    Channel -->|Message| User
```

---

## 2. Directory Structure

The codebase is organized as a monorepo workspace.

```
/
├── apps/                   # Client applications (Mobile/Desktop)
│   ├── android/            # Android client
│   ├── ios/                # iOS client
│   └── macos/              # macOS client
├── extensions/             # Messaging channels & plugins (Workspace Packages)
│   ├── discord/            # @autocrab/discord
│   ├── slack/              # @autocrab/slack
│   ├── telegram/           # @autocrab/telegram
│   └── ...                 # Signal, WhatsApp, etc.
├── packages/               # Shared libraries & specific bot implementations
├── scripts/                # Build, test, and maintenance scripts
├── src/                    # Core Gateway & CLI Source Code
│   ├── agents/             # Agent logic, tools, and runtime
│   ├── cli/                # Command-line interface implementation
│   ├── config/             # Configuration schema, loading, and validation
│   ├── gateway/            # Core server logic (Auth, HTTP, Plugin Loader)
│   ├── plugin-sdk/         # SDK for developing extensions
│   └── ...
└── ...
```

---

## 3. Core Components

### 3.1 The Gateway (`src/gateway`)

The Gateway is the kernel of AutoCrab. It differs significantly from the original OpenClaw implementation through extensive modularization and security hardening.

- **`src/gateway/auth/`**: Contains the Authentication Mode Policy engine. It enforces strict separation between authentication methods (Token vs. Password vs. Trusted Proxy) to prevent bypass vulnerabilities.
- **`src/gateway/http/`**: Handles the HTTP/WebSocket server, routing requests to appropriate internal handlers or extensions.
- **`src/gateway/plugins/`**: The Extension Loader. It dynamically loads plugins from the `extensions/` directory, validating their manifest (`autocrab.plugin.json`) and permissions before execution.
- **`src/gateway/server/`**: The main server loop and lifecycle management.

### 3.2 Agents & Tools (`src/agents`)

Agents are the intelligent workers.

- **Agent Runtime**: Powered by `@mariozechner/pi-agent-core`, handling the ReAct loop (Reasoning + Acting).
- **Tools**: Located in `src/agents/tools/` and `skills/`. These provide capabilities like Web Search, File I/O, and specialized integrations.
- **Sandboxing**: Agents can run in Dockerized sandboxes (configured via `docker-compose.yml`) for secure execution of code or untrusted tools.

### 3.3 Extensions (`extensions/`)

AutoCrab uses a capability-based extension system. Unlike the monolithic approach of its predecessor, core channels are implemented as independent workspace packages.

- **Structure**: Each extension acts as a standalone NPM package with its own `package.json` and build process.
- **Isolation**: Extensions interface with the Gateway through the `plugin-sdk`, ensuring they cannot access core internal state directly.
- **Workspace Packages**:
  - `@autocrab/discord`
  - `@autocrab/slack`
  - `@autocrab/telegram`
  - `@autocrab/signal`

### 3.4 CLI (`src/cli`)

The `autocrab` CLI is the primary management interface.

- **`onboard`**: Interactive wizard for simplified setup.
- **`configure`**: Manages the persistent configuration (stored in `~/.autocrab/` or mounted Docker volume). Supports secure key management for providers (e.g., Brave, Perplexity).
- **`doctor`**: Diagnostic tool to verify environment health, check for legacy "OpenClaw" artifacts, and validate configuration.

### 3.5 Configuration (`src/config`)

Configuration is managed via a robust schema validation system (Zod-based).

- **Configuration Flow**: Defauts -> Environment Variables -> Config File (`autocrab.json`) -> Runtime Overrides.
- **Security**: Sensitive values (API keys) can be securely referenced or injected via environment variables (e.g., `AUTOCRAB_GATEWAY_TOKEN`).

---

## 4. Client Applications (`apps/`)

AutoCrab includes native clients for seamless interaction:

- **Android (`apps/android`)**: Native Android app handling voice and text interaction.
- **iOS (`apps/ios`)**: Native iOS app.
- **macOS (`apps/macos`)**: Swift-based macOS client that can act as a voice gateway and system controller.

---

## 5. Security Architecture

This fork introduces a "Security-First" approach:

1.  **Supply Chain Policy**: `pnpm.onlyBuiltDependencies` allowlist restricts which packages can run install scripts, blocking malicious dependency attacks.
2.  **Authentication Policy**: Explicit conflict resolution in `gateway/auth` ensures no improved auth mode (like Trusted Proxy) accidentally opens the door to unauthenticated access if misconfigured.
3.  **Variable Sanitization**: CI/CD pipelines have been scrubbed of legacy `OPENCLAW_*` variables to prevent confusion and potential secret leakage.
4.  **Sandbox Isolation**: Docker-based sandboxing for agent execution protects the host system.

---

## 6. Technology Stack

- **Runtime**: Node.js 22+ (ESM architecture)
- **Language**: TypeScript 5.x (Strict Mode enabled)
- **Package Manager**: pnpm (Monorepo Workspace)
- **Containerization**: Docker / Podman
- **Testing**: Vitest (Unit & E2E)
- **Linting/Formatting**: Oxlint / Biome

---

_Document maintained by Dr Leshi Chen._
