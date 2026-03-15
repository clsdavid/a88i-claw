---
summary: "CLI reference for `autocrab secrets` (reload, audit, configure, apply)"
read_when:
  - Re-resolving secret refs at runtime
  - Auditing plaintext residues and unresolved refs
  - Configuring SecretRefs and applying one-way scrub changes
title: "secrets"
---

# `autocrab secrets`

Use `autocrab secrets` to manage SecretRefs and keep the active runtime snapshot healthy.

Command roles:

- `reload`: gateway RPC (`secrets.reload`) that re-resolves refs and swaps runtime snapshot only on full success (no config writes).
- `audit`: read-only scan of configuration/auth stores and legacy residues for plaintext, unresolved refs, and precedence drift.
- `configure`: interactive planner for provider setup, target mapping, and preflight (TTY required).
- `apply`: execute a saved plan (`--dry-run` for validation only), then scrub targeted plaintext residues.

Recommended operator loop:

```bash
autocrab secrets audit --check
autocrab secrets configure
autocrab secrets apply --from /tmp/autocrab-secrets-plan.json --dry-run
autocrab secrets apply --from /tmp/autocrab-secrets-plan.json
autocrab secrets audit --check
autocrab secrets reload
```

Exit code note for CI/gates:

- `audit --check` returns `1` on findings.
- unresolved refs return `2`.

Related:

- Secrets guide: [Secrets Management](/gateway/secrets)
- Credential surface: [SecretRef Credential Surface](/reference/secretref-credential-surface)
- Security guide: [Security](/gateway/security)

## Reload runtime snapshot

Re-resolve secret refs and atomically swap runtime snapshot.

```bash
autocrab secrets reload
autocrab secrets reload --json
```

Notes:

- Uses gateway RPC method `secrets.reload`.
- If resolution fails, gateway keeps last-known-good snapshot and returns an error (no partial activation).
- JSON response includes `warningCount`.

## Audit

Scan AutoCrab state for:

- plaintext secret storage
- unresolved refs
- precedence drift (`auth-profiles.json` credentials shadowing `autocrab.json` refs)
- legacy residues (legacy auth store entries, OAuth reminders)

```bash
autocrab secrets audit
autocrab secrets audit --check
autocrab secrets audit --json
```

Exit behavior:

- `--check` exits non-zero on findings.
- unresolved refs exit with higher-priority non-zero code.

Report shape highlights:

- `status`: `clean | findings | unresolved`
- `summary`: `plaintextCount`, `unresolvedRefCount`, `shadowedRefCount`, `legacyResidueCount`
- finding codes:
  - `PLAINTEXT_FOUND`
  - `REF_UNRESOLVED`
  - `REF_SHADOWED`
  - `LEGACY_RESIDUE`

## Configure (interactive helper)

Build provider and SecretRef changes interactively, run preflight, and optionally apply:

```bash
autocrab secrets configure
autocrab secrets configure --plan-out /tmp/autocrab-secrets-plan.json
autocrab secrets configure --apply --yes
autocrab secrets configure --providers-only
autocrab secrets configure --skip-provider-setup
autocrab secrets configure --agent ops
autocrab secrets configure --json
```

Flow:

- Provider setup first (`add/edit/remove` for `secrets.providers` aliases).
- Credential mapping second (select fields and assign `{source, provider, id}` refs).
- Preflight and optional apply last.

Flags:

- `--providers-only`: configure `secrets.providers` only, skip credential mapping.
- `--skip-provider-setup`: skip provider setup and map credentials to existing providers.
- `--agent <id>`: scope `auth-profiles.json` target discovery and writes to one agent store.

Notes:

- Requires an interactive TTY.
- You cannot combine `--providers-only` with `--skip-provider-setup`.
- `configure` targets secret-bearing fields in `autocrab.json` plus `auth-profiles.json` for the selected agent scope.
- `configure` supports creating new `auth-profiles.json` mappings directly in the picker flow.
- Canonical supported surface: [SecretRef Credential Surface](/reference/secretref-credential-surface).
- It performs preflight resolution before apply.
- Generated plans default to scrub options (`scrubEnv`, `scrubAuthProfilesForProviderTargets`, `scrubLegacyAuthJson` all enabled).
- Apply path is one-way for scrubbed plaintext values.
- Without `--apply`, CLI still prompts `Apply this plan now?` after preflight.
- With `--apply` (and no `--yes`), CLI prompts an extra irreversible confirmation.

Exec provider safety note:

- Homebrew installs often expose symlinked binaries under `/opt/homebrew/bin/*`.
- Set `allowSymlinkCommand: true` only when needed for trusted package-manager paths, and pair it with `trustedDirs` (for example `["/opt/homebrew"]`).
- On Windows, if ACL verification is unavailable for a provider path, AutoCrab fails closed. For trusted paths only, set `allowInsecurePath: true` on that provider to bypass path security checks.

## Apply a saved plan

Apply or preflight a plan generated previously:

```bash
autocrab secrets apply --from /tmp/autocrab-secrets-plan.json
autocrab secrets apply --from /tmp/autocrab-secrets-plan.json --dry-run
autocrab secrets apply --from /tmp/autocrab-secrets-plan.json --json
```

Plan contract details (allowed target paths, validation rules, and failure semantics):

- [Secrets Apply Plan Contract](/gateway/secrets-plan-contract)

What `apply` may update:

- `autocrab.json` (SecretRef targets + provider upserts/deletes)
- `auth-profiles.json` (provider-target scrubbing)
- legacy `auth.json` residues
- `~/.autocrab/.env` known secret keys whose values were migrated

## Why no rollback backups

`secrets apply` intentionally does not write rollback backups containing old plaintext values.

Safety comes from strict preflight + atomic-ish apply with best-effort in-memory restore on failure.

## Example

```bash
autocrab secrets audit --check
autocrab secrets configure
autocrab secrets audit --check
```

If `audit --check` still reports plaintext findings, update the remaining reported target paths and rerun audit.
