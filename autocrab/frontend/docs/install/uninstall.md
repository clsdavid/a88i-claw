---
summary: "Uninstall AutoCrab completely (CLI, service, state, workspace)"
read_when:
  - You want to remove AutoCrab from a machine
  - The gateway service is still running after uninstall
title: "Uninstall"
---

# Uninstall

Two paths:

- **Easy path** if `autocrab` is still installed.
- **Manual service removal** if the CLI is gone but the service is still running.

## Easy path (CLI still installed)

Recommended: use the built-in uninstaller:

```bash
autocrab uninstall
```

Non-interactive (automation / npx):

```bash
autocrab uninstall --all --yes --non-interactive
npx -y autocrab uninstall --all --yes --non-interactive
```

Manual steps (same result):

1. Stop the gateway service:

```bash
autocrab gateway stop
```

2. Uninstall the gateway service (launchd/systemd/schtasks):

```bash
autocrab gateway uninstall
```

3. Delete state + config:

```bash
rm -rf "${AUTOCRAB_STATE_DIR:-$HOME/.autocrab}"
```

If you set `AUTOCRAB_CONFIG_PATH` to a custom location outside the state dir, delete that file too.

4. Delete your workspace (optional, removes agent files):

```bash
rm -rf ~/.autocrab/workspace
```

5. Remove the CLI install (pick the one you used):

```bash
npm rm -g autocrab
pnpm remove -g autocrab
bun remove -g autocrab
```

6. If you installed the macOS app:

```bash
rm -rf /Applications/AutoCrab.app
```

Notes:

- If you used profiles (`--profile` / `AUTOCRAB_PROFILE`), repeat step 3 for each state dir (defaults are `~/.autocrab-<profile>`).
- In remote mode, the state dir lives on the **gateway host**, so run steps 1-4 there too.

## Manual service removal (CLI not installed)

Use this if the gateway service keeps running but `autocrab` is missing.

### macOS (launchd)

Default label is `ai.autocrab.gateway` (or `ai.autocrab.<profile>`; legacy `com.autocrab.*` may still exist):

```bash
launchctl bootout gui/$UID/ai.autocrab.gateway
rm -f ~/Library/LaunchAgents/ai.autocrab.gateway.plist
```

If you used a profile, replace the label and plist name with `ai.autocrab.<profile>`. Remove any legacy `com.autocrab.*` plists if present.

### Linux (systemd user unit)

Default unit name is `autocrab-gateway.service` (or `autocrab-gateway-<profile>.service`):

```bash
systemctl --user disable --now autocrab-gateway.service
rm -f ~/.config/systemd/user/autocrab-gateway.service
systemctl --user daemon-reload
```

### Windows (Scheduled Task)

Default task name is `AutoCrab Gateway` (or `AutoCrab Gateway (<profile>)`).
The task script lives under your state dir.

```powershell
schtasks /Delete /F /TN "AutoCrab Gateway"
Remove-Item -Force "$env:USERPROFILE\.autocrab\gateway.cmd"
```

If you used a profile, delete the matching task name and `~\.autocrab-<profile>\gateway.cmd`.

## Normal install vs source checkout

### Normal install (install.sh / npm / pnpm / bun)

If you used `https://autocrab.ai/install.sh` or `install.ps1`, the CLI was installed with `npm install -g autocrab@latest`.
Remove it with `npm rm -g autocrab` (or `pnpm remove -g` / `bun remove -g` if you installed that way).

### Source checkout (git clone)

If you run from a repo checkout (`git clone` + `autocrab ...` / `bun run autocrab ...`):

1. Uninstall the gateway service **before** deleting the repo (use the easy path above or manual service removal).
2. Delete the repo directory.
3. Remove state + workspace as shown above.
