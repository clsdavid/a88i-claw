---
summary: "CLI reference for `autocrab logs` (tail gateway logs via RPC)"
read_when:
  - You need to tail Gateway logs remotely (without SSH)
  - You want JSON log lines for tooling
title: "logs"
---

# `autocrab logs`

Tail Gateway file logs over RPC (works in remote mode).

Related:

- Logging overview: [Logging](/logging)

## Examples

```bash
autocrab logs
autocrab logs --follow
autocrab logs --json
autocrab logs --limit 500
autocrab logs --local-time
autocrab logs --follow --local-time
```

Use `--local-time` to render timestamps in your local timezone.
