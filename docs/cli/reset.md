---
summary: "CLI reference for `autocrab reset` (reset local state/config)"
read_when:
  - You want to wipe local state while keeping the CLI installed
  - You want a dry-run of what would be removed
title: "reset"
---

# `autocrab reset`

Reset local config/state (keeps the CLI installed).

```bash
autocrab reset
autocrab reset --dry-run
autocrab reset --scope config+creds+sessions --yes --non-interactive
```
