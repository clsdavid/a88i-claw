---
name: mcp
description: Model Context Protocol (external tools)
---

# Skill: MCP (Model Context Protocol)

The MCP skill allows you to interact with external tool providers (like `mcp.test`) that host dynamic tools for various domains (Forex, Crypto, Stocks, News, etc.).

## Tools

### 1. `mcp_list`

Lists all available tools from the external provider. Use this first to discover what's available.

### 2. `mcp_help`

Gets detailed documentation and required JSON payload structure for a specific tool. **Always call this before running a new tool.**

- **Arguments:**
  - `tool_name`: The name of the tool to inspect.

### 3. `mcp_run`

Executes a specific tool with a provided input payload.

- **Arguments:**
  - `tool_name`: The name of the tool to run.
  - `input_data`: A JSON object (dictionary) containing the arguments required by the tool.

## Typical Workflow

1. **Discovery**: `mcp_list()` -> Returns a list of tool names.
2. **Inspection**: `mcp_help(tool_name="get_latest_price_of_forex")` -> Returns details on how to build the payload.
3. **Execution**: `mcp_run(tool_name="get_latest_price_of_forex", input_data={"currency_pair": "EUR/USD"})` -> Returns the live data.

## Important Notes

- MCP tools are "live" and usually require an active internet connection.
- If a tool fails, it might be due to incorrect `input_data` or a temporary server issue.
- Do not guess the `input_data`; always use `mcp_help` first.
