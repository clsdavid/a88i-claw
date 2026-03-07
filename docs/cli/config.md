---
summary: "CLI reference for `autocrab config` (get/set/unset/file/validate)"
read_when:
  - You want to read or edit config non-interactively
title: "config"
---

# `autocrab config`

Config helpers: get/set/unset/validate values by path and print the active
config file. Run without a subcommand to open
the configure wizard (same as `autocrab configure`).

## Examples

```bash
autocrab config file
autocrab config get browser.executablePath
autocrab config set browser.executablePath "/usr/bin/google-chrome"
autocrab config set agents.defaults.heartbeat.every "2h"
autocrab config set agents.list[0].tools.exec.node "node-id-or-name"
autocrab config unset tools.web.search.apiKey
autocrab config validate
autocrab config validate --json
```

## Paths

Paths use dot or bracket notation:

```bash
autocrab config get agents.defaults.workspace
autocrab config get agents.list[0].id
```

Use the agent list index to target a specific agent:

```bash
autocrab config get agents.list
autocrab config set agents.list[1].tools.exec.node "node-id-or-name"
```

## Values

Values are parsed as JSON5 when possible; otherwise they are treated as strings.
Use `--strict-json` to require JSON5 parsing. `--json` remains supported as a legacy alias.

```bash
autocrab config set agents.defaults.heartbeat.every "0m"
autocrab config set gateway.port 19001 --strict-json
autocrab config set channels.whatsapp.groups '["*"]' --strict-json
```

## Subcommands

- `config file`: Print the active config file path (resolved from `AUTOCRAB_CONFIG_PATH` or default location).

Restart the gateway after edits.

## Validate

Validate the current config against the active schema without starting the
gateway.

```bash
autocrab config validate
autocrab config validate --json
```
