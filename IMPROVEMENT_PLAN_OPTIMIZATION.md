# Improvement Plan: Token Usage Optimization & Security Audit

## Status

- **Date**: 2024-05-24
- **Focus**: Performance (Token Usage) and Security

## Token Usage Analysis

### 1. Infinite History Default

**Issue**: The `src/agents/pi-embedded-runner/history.ts` logic defines `limitHistoryTurns` such that if `limit` is undefined or 0, it returns the _full_ message history. The configuration helper `getHistoryLimitFromSessionKey` returns `undefined` if the user hasn't explicitly set a `historyLimit` in their `channels` config.
**Impact**: For long-running conversations (especially in DMs or Channels), the context window grows linearly with every turn until the provider's limit is hit. This causes:

- Increasing cost per turn.
- Increasing latency (processing more input tokens).
- "Context stuffing" where the model forgets earlier instructions due to noise.

**Proposed Fix**:

- Change `getHistoryLimitFromSessionKey` in `src/agents/pi-embedded-runner/history.ts` to fallback to a reasonable default (e.g., 30 or 50 turns) instead of `undefined` when no config is present.
- Alternatively, enforce a default in `src/config/defaults.ts` that merges into the loaded config.

### 2. "Heavy" System Prompt

**Issue**: `src/agents/system-prompt.ts` constructs a comprehensive system prompt that includes:

- **Skills Section**: Generic instructions for skill loading.
- **Memory Section**: Detailed rules for memory management.
- **Messaging Section**: Routing and tool usage instructions.
- **Tool Definitions**: A list of 20+ tools with descriptions.
  **Impact**: A high "base cost" for every request, even for simple "hello" messages.

**Proposed Fix**:

- **Dynamic Section Loading**: Only include the "Memory" section if memory tools are actually enabled/relevant.
- **Minimization**: Use `PromptMode="minimal"` for sub-agents or specific channel types where full capabilities aren't needed.
- **Tool Description Optimization**: Shorten tool descriptions in `coreToolSummaries` where possible.

## Security Audit Findings

### 1. Hardcoded Secrets

- **Scan Result**: Ran grep searches for common prefixes (`sk-proj-`, `xoxb-`, `ghp_`).
- **Finding**: No active hardcoded secrets found in source code. Matches were limited to:
  - Test fixtures (`test/fixtures/*`)
  - Placeholder values in documentation or comments.
- **Conclusion**: The codebase practices good secret hygiene (relying on env vars and config).

### 2. Execution Sandbox

- **Risk**: The `exec` tool allows arbitrary shell command execution.
- **Mitigation**:
  - The system prompt explicitly instructs against using `exec` for messaging.
  - `buildUserIdentitySection` implies an "Authorized Senders" allowlist.
- **Recommendation**: Ensure `ownerNumbers` / allowlists are strictly enforced before allowing `exec` tool usage in channel-based agents.

## Actionable Recommendations for User

1.  **Configure History Limit**:
    Add `"historyLimit": 50` to your `autocrab` config (e.g., in `~/.autocrab/config.json`) under the relevant channel provider.

    ```json
    {
      "channels": {
        "discord": {
          "historyLimit": 50
        }
      }
    }
    ```

2.  **Review Authorized Users**:
    Ensure your `owner` or allowlist is configured to prevent unauthorized users from accessing the `exec` tool via public channels.
