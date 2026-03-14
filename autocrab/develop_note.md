Compatibility and Feature Parity Plan
Goal Description
Implement missing features in the Python port (autocrab/) to ensure full compatibility and 1:1 feature parity with the original Node.js AutoCrab implementation, fulfilling the requirements of "Phase 5". The focus is on missing core agent tools (Browser, FS) and ensuring the REST/WebSocket gateway endpoints accurately reflect the original capabilities and schemas constraint.

Proposed Changes
Core Tools Parity
The Python port is missing the fundamental Filesystem (FS) and
Browser
tools outlined in Phase 3 of the
ARCHITECTURE_PYTHON.md
.

[NEW]
fs.py
(file:///home/chenl/Projects/a88i-claw/autocrab/src/autocrab/core/tools/fs.py)
Implement FS capabilities (read, write, list directories). This must be constrained by the
SandboxManager
to execute inside the isolated Docker container to match the security profile of the original implementation.

[NEW]
browser.py
(file:///home/chenl/Projects/a88i-claw/autocrab/src/autocrab/core/tools/browser.py)
Implement the
Browser
automation tool schema. This will interface with the
sandbox-browser
Docker container (using the Docker SDK) to perform web interactions, mirroring the capabilities of the original Playwright-based Node.js browser-tool.

Agent Graph Integration
The new tools must be registered with the Brain.

[MODIFY]
graph.py
(file:///home/chenl/Projects/a88i-claw/autocrab/src/autocrab/core/agent/graph.py)
Import
fs
and
browser
tools and add them to the available toolset passed to the
ChatOpenAI
model and handled by the
execute_tools
Graph Node.

API Gateway Data Parity
The Gateway must support advanced fields from the
CreateResponseBody
schema to ensure 1:1 compatibility with the frontend CLI/Web apps.

[MODIFY]
main.py
(file:///home/chenl/Projects/a88i-claw/autocrab/src/autocrab/core/gateway/main.py)
POST /v1/responses: Update to properly ingest and route schema fields like tool_choice,
stream
, and instructions into the initial_state of the LangGraph agent executor.
GET /ws/v1/events: Ensure the WebSocket properly wraps the LangGraph stream events, parsing tool execution updates (AgentAction) to match the original OpenResponses stream format, rather than just returning a final text block.
Verification Plan
Automated Tests
Write and run pytest -v tests/unit/tools/test_fs.py and pytest -v tests/unit/tools/test_browser.py to verify tool logic.
Run existing pytest -v tests/ to ensure no regressions in current features.
Manual Verification
Boot the Python Gateway: uvicorn autocrab.core.gateway.main:app --port 8000
Manually POST to /v1/responses with a prompt to "check google.com" to verify Browser tool routing.
Code Review: Configuration & Agent Loading Parity
As Project Manager, I have reviewed the Python backend (autocrab/src/) against ARCHITECTURE_PYTHON.md and the original Node.js implementation (src/).

Findings: Currently, the Python backend (config.py) only parses basic setup from .env constraints using pydantic-settings. It fails to load the user's primary ~/.autocrab/autocrab.json configuration file. Furthermore, the LangGraph agents are hardcoded to a single .sessions directory rather than dynamically parsing agents.list to isolate states into ~/.autocrab/agents/<id>/agent/ as required by the original security layout.

Proposed Changes for 1:1 Parity:

Configuration Loader (autocrab/src/autocrab/core/models/config.py)
[MODIFY] config.py: Rewrite AutoCrabSettings to read from both the ~/.autocrab/autocrab.json JSON5 file and .env variables. Pydantic's settings_sources or a custom initialization script will merge these.
Add AgentsConfig, AuthConfig, and ModelsConfig sub-models to closely match the original zod-schema.agents.ts and types.autocrab.ts layout.
Agent Environment Setup (autocrab/src/autocrab/core/agent/graph.py)
[MODIFY] graph.py or the initialization hook: Ensure that the graph loads the specific LLM model defined for the target agent inside agents.list rather than a global LLM.
[MODIFY] memory.py (or relevant session storage): Route SQLite and file-based tool session states dynamically into ~/.autocrab/agents/<agent_id>/agent/sessions/ rather than a flat .sessions/ folder.
Verification Plan
Ensure the gateway boots successfully when a complex multi-agent ~/.autocrab/autocrab.json is present.
Verify that chat logs / interactions are persisted to the correct ~/.autocrab/agents/<id>/agent/ sub-directories.
Workspace Permanent Memory Support
Per user request, the agent needs to pull "permanent memory" bindings from ./autocrab/workspace (specifically the MEMORY.md file), matching the original node.js implementation behavior.

Findings: The original Application reads MEMORY.md or memory.md located in an agent's workspace_dir and treats it as core guidelines for the agent. Currently, HybridMemoryStore inside memory.py only serves conversational transcript chunks and external RAG chunks. It completely misses reading the static instruction memory set within the workspace.

Proposed Changes for Support:

Workspace Resolution & Memory Injection (autocrab/src/autocrab/core/agent/memory.py)
[MODIFY] memory.py: Add load_permanent_memory to HybridMemoryStore.
We will resolve the workspace based on the strict fallback priority found in the original TS equivalent (resolveAgentWorkspaceDir):
agent_config.workspace (if explicitly defined in autocrab.json agents list)
./autocrab/workspace (if the agent is the default fallback)
~/.autocrab/workspace-<agent_id> (isolated fallback for non-default agents)
Implement file reading pointing to MEMORY.md or memory.md within that directory.
Update get_context to prepend the permanent memory block ahead of the dynamic RAG / flat-file history.
Verification Plan
Create a dummy test file ./autocrab/workspace/MEMORY.md containing generic permanent guidance.
Initialize test_config2.py simulating graph execution, and print out the injected system context to verify the <PERMANENT_MEMORY> payload appears correctly.
Phase 6: Ecosystem Component Migration Strategy
The user has pointed out that the original root src/ contains many specialized components (e.g., channels, tui, wizard, pairing, i18n, tts, web, discord, telegram) that are seemingly missing from the lean autocrab/core Python architecture.

To achieve a true professional decoupling, not everything from the Node.js monolith should go into autocrab/core. We will propose the following migration mapping:

1. The Core Extension (To be added to autocrab/core/)
   compat/, routing/, sessions/: Abstract interfaces for session management and HTTP routing belong in the core API gateway.
   security/, secrets/: Essential infrastructure for handling auth and API keys natively.
2. The Plugin System (To be added to autocrab/plugins/)
   channels/\* (e.g. discord, telegram, slack, web): These should be implemented as separate Python plugin modules utilizing importlib or Celery workers. They do not belong in the core event loop.
   tools/ and media-understanding: Specific tool sets should be built as @autocrab.skill() decorated plugins or separate MCP servers.
3. Deprecated or Delegated (Do not port to Backend)
   tui/, wizard/, canvas-host/: The Python backend is designed to be a headless API. Rendering UI logic should remain strictly within the Lit Web UI or Swift/Kotlin clients.
   pairing/: If handled by the new authentication schemas natively, the old manual pairing flow is obsolete.
   Verification Plan For Phase 6:

Catalog all remaining directories in src/ and officially assign them to one of the 3 outcomes above.
Create stub directories in autocrab/plugins/ to demonstrate where channels will live natively.
