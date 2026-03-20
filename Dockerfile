FROM node:22-bookworm@sha256:f90672bf4c76dfc077d17be4c115b1ae7731d2e8558b457d86bca42aeb193866

# OCI base-image metadata for downstream image consumers.
# If you change these annotations, also update:
# - docs/install/docker.md ("Base image metadata" section)
# - https://docs.autocrab.ai/install/docker
LABEL org.opencontainers.image.base.name="docker.io/library/node:22-bookworm" \
  org.opencontainers.image.base.digest="sha256:cd7bcd2e7a1e6f72052feb023c7f6b722205d3fcab7bbcbd2d1bfdab10b1e935" \
  org.opencontainers.image.source="https://github.com/clsdavid/autocrab" \
  org.opencontainers.image.url="https://autocrab.ai" \
  org.opencontainers.image.documentation="https://docs.autocrab.ai/install/docker" \
  org.opencontainers.image.licenses="MIT" \
  org.opencontainers.image.title="AutoCrab" \
  org.opencontainers.image.description="AutoCrab gateway and CLI runtime container image"

# Install Bun (required for build scripts)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

RUN corepack enable

WORKDIR /app
RUN chown node:node /app

ARG AUTOCRAB_DOCKER_APT_PACKAGES=""
RUN if [ -n "$AUTOCRAB_DOCKER_APT_PACKAGES" ]; then \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $AUTOCRAB_DOCKER_APT_PACKAGES && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*; \
  fi

COPY --chown=node:node package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY --chown=node:node ui/package.json ./ui/package.json
COPY --chown=node:node patches ./patches
COPY --chown=node:node scripts ./scripts

USER node
# Reduce OOM risk on low-memory hosts during dependency installation.
# Docker builds on small VMs may otherwise fail with "Killed" (exit 137).
RUN NODE_OPTIONS=--max-old-space-size=2048 pnpm install --frozen-lockfile

# Optionally install Chromium and Xvfb for browser automation.
# Build with: docker build --build-arg AUTOCRAB_INSTALL_BROWSER=1 ...
# Adds ~300MB but eliminates the 60-90s Playwright install on every container start.
# Must run after pnpm install so playwright-core is available in node_modules.
USER root
ARG AUTOCRAB_INSTALL_BROWSER=""
RUN if [ -n "$AUTOCRAB_INSTALL_BROWSER" ]; then \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xvfb && \
  mkdir -p /home/node/.cache/ms-playwright && \
  PLAYWRIGHT_BROWSERS_PATH=/home/node/.cache/ms-playwright \
  node /app/node_modules/playwright-core/cli.js install --with-deps chromium && \
  chown -R node:node /home/node/.cache/ms-playwright && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*; \
  fi

# Optionally install Docker CLI for sandbox container management.
# Build with: docker build --build-arg AUTOCRAB_INSTALL_DOCKER_CLI=1 ...
# Adds ~50MB. Only the CLI is installed — no Docker daemon.
# Required for agents.defaults.sandbox to function in Docker deployments.
ARG AUTOCRAB_INSTALL_DOCKER_CLI=""
ARG AUTOCRAB_DOCKER_GPG_FINGERPRINT="9DC858229FC7DD38854AE2D88D81803C0EBFCD88"
RUN if [ -n "$AUTOCRAB_INSTALL_DOCKER_CLI" ]; then \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg && \
  install -m 0755 -d /etc/apt/keyrings && \
  # Verify Docker apt signing key fingerprint before trusting it as a root key.
  # Update AUTOCRAB_DOCKER_GPG_FINGERPRINT when Docker rotates release keys.
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /tmp/docker.gpg.asc && \
  expected_fingerprint="$(printf '%s' "$AUTOCRAB_DOCKER_GPG_FINGERPRINT" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')" && \
  actual_fingerprint="$(gpg --batch --show-keys --with-colons /tmp/docker.gpg.asc | awk -F: '$1 == "fpr" { print toupper($10); exit }')" && \
  if [ -z "$actual_fingerprint" ] || [ "$actual_fingerprint" != "$expected_fingerprint" ]; then \
  echo "ERROR: Docker apt key fingerprint mismatch (expected $expected_fingerprint, got ${actual_fingerprint:-<empty>})" >&2; \
  exit 1; \
  fi && \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg /tmp/docker.gpg.asc && \
  rm -f /tmp/docker.gpg.asc && \
  chmod a+r /etc/apt/keyrings/docker.gpg && \
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable\n' \
  "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/docker.list && \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  docker-ce-cli docker-compose-plugin && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*; \
  fi

USER node
COPY --chown=node:node . .

# Ensure default template files exist if they were excluded from the build context
# (for example if IDENTITY.md/USER.md are locally untracked but required by runtime).
RUN for name in IDENTITY USER MEMORY; do \
  if [ ! -f "docs/reference/templates/${name}.md" ] && [ -f "docs/reference/templates/${name}.dev.md" ]; then \
  cp "docs/reference/templates/${name}.dev.md" "docs/reference/templates/${name}.md"; \
  fi; \
  done

# Normalize copied plugin/agent paths so plugin safety checks do not reject
# world-writable directories inherited from source file modes.
RUN for dir in /app/extensions /app/.agent /app/.agents; do \
  if [ -d "$dir" ]; then \
  find "$dir" -type d -exec chmod 755 {} +; \
  find "$dir" -type f -exec chmod 644 {} +; \
  fi; \
  done

# Ensure workspace packages (extensions) are linked and their dependencies installed
# since they were not available during the initial pnpm install step.
RUN pnpm install

RUN pnpm build
# Force pnpm for UI build (Bun may fail on ARM/Synology architectures)
ENV AUTOCRAB_PREFER_PNPM=1
RUN pnpm ui:build

# Expose the CLI binary without requiring npm global writes as non-root.
USER root
RUN ln -sf /app/autocrab.mjs /usr/local/bin/autocrab \
  && chmod 755 /app/autocrab.mjs

ENV NODE_ENV=production

# Security hardening: Run as non-root user
# The node:22-bookworm image includes a 'node' user (uid 1000)
# This reduces the attack surface by preventing container escape via root privileges
USER node

# Start gateway server with default config.
# Binds to loopback (127.0.0.1) by default for security.
#
# IMPORTANT: With Docker bridge networking (-p 18789:18789), loopback bind
# makes the gateway unreachable from the host. Either:
#   - Use --network host, OR
#   - Override --bind to "lan" (0.0.0.0) and set auth credentials
#
# Built-in probe endpoints for container health checks:
#   - GET /healthz (liveness) and GET /readyz (readiness)
#   - aliases: /health and /ready
# For external access from host/ingress, override bind to "lan" and set auth.
HEALTHCHECK --interval=3m --timeout=10s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:18789/healthz').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "autocrab.mjs", "gateway", "--allow-unconfigured"]
