# Improvement Plan: Token Usage Optimization & Security Audit

## Status

- **Date**: 2024-05-24 (Updated 2026-03-10)
- **Focus**: Performance (Token Usage) and Security
- **Completion**: Phase 1 technical fixes applied on 2026-03-10.

## Token Usage Analysis

### 1. Infinite History Default (Fixed)

**Issue**: The `src/agents/pi-embedded-runner/history.ts` logic defines `limitHistoryTurns` such that if `limit` is undefined or 0, it returns the _full_ message history.
**Fix Applied**:

- Added `DEFAULT_HISTORY_LIMIT = 50` in `src/agents/defaults.ts`.
- Updated `src/agents/pi-embedded-runner/history.ts` to use this default when no explicit configuration is found.

### 2. "Heavy" System Prompt (Optimized)

**Issue**: `src/agents/system-prompt.ts` constructs a comprehensive system prompt with significant overhead.
**Fix Applied**:

- **Dynamic Messaging Section**: The prompt now skips the "Messaging" section if no messaging tools (`message`, `sessions_send`, `subagents`) are available.
- **Tool Description Optimization**: Shortened descriptions for `cron`, `agents_list`, `sessions_spawn`, and `session_status`.

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
