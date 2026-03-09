# AutoCrab Architecture

**Original Source:** Forked from OpenClaw 3.3.
**Modifications:** Extensive security hardening, architectural refactoring, and rebranding by Dr Leshi Chen.
**License:** MIT (See [LICENSE](LICENSE))

---

## 1. System Overview

AutoCrab is a personal AI assistant gateway that bridges Large Language Models (LLMs) with various messaging channels and local device capabilities. It is designed to be self-hosted, secure, and extensible.

### Core Components

- **Gateway:** The central server that manages state, authentication, and routing between agents and channels.
- **Agents:** Intelligent entities (powered by `@mariozechner/pi-agent-core`) that process user input and execute tools.
- **Extensions (Channels):** Plugins that connect the gateway to external platforms (Discord, Slack, Telegram, Signal, etc.).
- **CLI:** Command-line interface for management, configuration, and diagnostics.

---

## 2. Key Improvements & Refactoring

This version of AutoCrab includes significant architectural changes from the original OpenClaw 3.3 base:

### Security Hardening

- **Supply Chain Security:** Implemented `pnpm.onlyBuiltDependencies` to restrict install scripts to a strictly allowlisted set of packages, mitigating potential supply chain attacks.
- **CI/CD Sanitization:** Complete overhaul of GitHub Actions workflows to remove legacy variables and enforce strict Docker image push policies (preventing namespace hijacking).
- **Dependency Audit:** Removal of unused native modules (e.g., `authenticate-pam`, `koffi`) to reduce the attack surface.

### Architectural Modularization

- **Gateway Refactoring:** The monolithic `src/gateway` has been split into distinct functional domains:
  - `src/gateway/auth/`: Dedicated authentication logic and Auth Mode Policy.
  - `src/gateway/http/`: HTTP server handling and routing.
  - `src/gateway/plugins/`: Extension loading and management.
- **Extension Isolation:** Core messaging channels (Discord, Slack, Telegram, Signal) were moved from `src/` to `extensions/` to standardize the plugin architecture and improve isolation.

### Deployment & Usability

- **Docker Optimization:** Enhanced `docker-compose.yml` to support local Ollama inference via `host.docker.internal` and robust volume mounting for configuration persistence.
- **Configuration Wizard:** Updated `autocrab configure` command to securely handle web search provider keys and other settings in a Docker-friendly manner.

---

## 3. Component Details

### 3.1 The Gateway (`src/gateway`)

The Gateway serves as the "brain" of the operation. It handles:

- **Authentication:** Enforces strict conflict detection between auth modes (token vs. password vs. trusted-proxy) via `src/gateway/auth-mode-policy.ts`.
- **Routing:** Directs messages from channels to the appropriate agent instance.
- **State Management:** Manages conversational history and user sessions.

### 3.2 Extensions (`extensions/`)

AutoCrab uses a capability-based extension system. Official channels are now maintained as workspace packages:

- `@autocrab/discord`
- `@autocrab/slack`
- `@autocrab/telegram`
- `@autocrab/signal`

This structure forces strict boundary checks and prevents tight coupling with the core gateway logic.

### 3.3 CLI (`src/cli`)

The `autocrab` CLI provides a unified interface for:

- **Onboarding:** `autocrab onboard`
- **Configuration:** `autocrab configure`
- **Diagnostics:** `autocrab doctor`
- **Server Management:** `autocrab gateway`

### 3.4 Runtime & Tech Stack

- **Runtime:** Node.js 22+ (ESM only)
- **Language:** TypeScript 5.x (Strict Mode)
- **Package Manager:** pnpm 9+ (Monorepo/Workspace)
- **Testing:** Vitest
- **Containerization:** Docker & Podman support

---

## 4. Licensing

This project is licensed under the MIT License.
**Copyright (c) 2026 Dr Leshi Chen <chenleshi@hotmail.com>**

For the full license text, please refer to the [LICENSE](LICENSE) file.
