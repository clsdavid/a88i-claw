---
summary: "CLI reference for `autocrab devices` (device pairing + token rotation/revocation)"
read_when:
  - You are approving device pairing requests
  - You need to rotate or revoke device tokens
title: "devices"
---

# `autocrab devices`

Manage device pairing requests and device-scoped tokens.

## Commands

### `autocrab devices list`

List pending pairing requests and paired devices.

```
autocrab devices list
autocrab devices list --json
```

### `autocrab devices remove <deviceId>`

Remove one paired device entry.

```
autocrab devices remove <deviceId>
autocrab devices remove <deviceId> --json
```

### `autocrab devices clear --yes [--pending]`

Clear paired devices in bulk.

```
autocrab devices clear --yes
autocrab devices clear --yes --pending
autocrab devices clear --yes --pending --json
```

### `autocrab devices approve [requestId] [--latest]`

Approve a pending device pairing request. If `requestId` is omitted, AutoCrab
automatically approves the most recent pending request.

```
autocrab devices approve
autocrab devices approve <requestId>
autocrab devices approve --latest
```

### `autocrab devices reject <requestId>`

Reject a pending device pairing request.

```
autocrab devices reject <requestId>
```

### `autocrab devices rotate --device <id> --role <role> [--scope <scope...>]`

Rotate a device token for a specific role (optionally updating scopes).

```
autocrab devices rotate --device <deviceId> --role operator --scope operator.read --scope operator.write
```

### `autocrab devices revoke --device <id> --role <role>`

Revoke a device token for a specific role.

```
autocrab devices revoke --device <deviceId> --role node
```

## Common options

- `--url <url>`: Gateway WebSocket URL (defaults to `gateway.remote.url` when configured).
- `--token <token>`: Gateway token (if required).
- `--password <password>`: Gateway password (password auth).
- `--timeout <ms>`: RPC timeout.
- `--json`: JSON output (recommended for scripting).

Note: when you set `--url`, the CLI does not fall back to config or environment credentials.
Pass `--token` or `--password` explicitly. Missing explicit credentials is an error.

## Notes

- Token rotation returns a new token (sensitive). Treat it like a secret.
- These commands require `operator.pairing` (or `operator.admin`) scope.
- `devices clear` is intentionally gated by `--yes`.
- If pairing scope is unavailable on local loopback (and no explicit `--url` is passed), list/approve can use a local pairing fallback.
