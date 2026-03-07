# AutoCrab Project Improvement Plan: Security & Architecture

**Date:** March 8, 2026
**Focus:** Security-First Architecture & Simplification

## Executive Summary

The AutoCrab project (formerly OpenClaw) has a strong foundational security posture but suffers from **inconsistent rebranding** and **monolithic architectural technical debt** that introduces potential risks. This report outlines a phased approach to remediation, prioritizing security stability and operational simplicity.

---

## 🛡️ Security Assessment

### Strengths

1.  **Transport Security**: Strong use of `crypto.timingSafeEqual` prevents timing attacks in secret comparison.
2.  **Authentication Policy**: `src/gateway/auth-mode-policy.ts` enforces strict conflict detection between auth modes (token vs. password vs. trusted-proxy).
3.  **CI/CD Hygiene**:
    - Minimal permission verify scopes in GitHub Workflows.
    - Active secret scanning (`detect-secrets`, `zizmor`) in CI.
    - Dependency lock-down via `pnpm.onlyBuiltDependencies`.
4.  **Trust Model**: explicit "single gateway per operator" model reduces multi-tenant complexity risks.

### Critical Gaps (Risk Areas)

1.  **Rename Inconsistency (High Risk)**: The incomplete rename from `OpenClaw` to `AutoCrab` has left `OPENCLAW_*` environment variables in CI/CD pipelines. This ambiguity can lead to **misconfiguration**, **failed secret injection**, or **deployment to wrong targets** (e.g., docker image names).
2.  **Gateway Monolith (Medium Risk)**: `src/gateway/` contains 150+ files mixing auth, network, and business logic. Complex codebases are harder to audit and easier to hide vulnerabilities in.
3.  **Dependency Confusion**: The mix of `src/` core channels vs. `extensions/` workspace packages creates two different security models for what should be identical functionality.

---

## 🚀 Improvement Phases

### Phase 1: Security Hygiene & Rename Completion (Immediate - 1 Week)

**Goal:** Eliminate confusion and ensure CI/CD security integrity.

1.  **CI/CD Variable Sanitization**:
    - Search and replace all `OPENCLAW_*` env vars in `.github/workflows/` to `AUTOCRAB_*`.
    - **Why**: Ensures secrets and config match the new project identity; prevents "silent failures" where a new secret is added but the old env var is read.
2.  **Docker Registry Security**:
    - Scan `.github/workflows/` for `openclaw` docker image references.
    - Update strict logic to push _only_ to `autocrab/*` repositories to prevent namespace hijacking.
3.  **Issue Template Fixing**:
    - Audit `.github/ISSUE_TEMPLATE/` to remove "OpenClaw" phrasing.
    - **Why**: Social engineering risk; users might be tricked into reporting sensitive info to old/wrong channels if confused.

### Phase 2: Gateway Hardening & Architecture (Short-Term - 1 Month)

**Goal:** Reduce the attack surface of the core Gateway.

1.  **Refactor `src/gateway`**:
    - Split the 150+ file directory into strict modules:
      - `src/gateway/auth/`: Only authentication logic.
      - `src/gateway/http/`: Server handling.
      - `src/gateway/plugins/`: Extension loading.
    - **Security Benefit**: Easier to audit `auth/` in isolation.
2.  **Auth Rate Limiting Documentation**:
    - Document the existing rate-limiting logic in `src/security/`.
    - Ensure "Trusted Proxy" mode has explicit warnings about `X-Real-IP` spoofing risks if misconfigured.

### Phase 3: Developer Experience & Standardization (Medium-Term - 3 Months)

**Goal:** Reduce human error during extension development.

1.  **Extension Scaffolding Tool**:
    - Create `scripts/create-extension.ts`.
    - **Security Benefit**: Ensures new extensions start with secure defaults (e.g., correct `package.json` permissions, pre-configured test harnesses) rather than copy-pasting potentially insecure boilerplate.
2.  **Standardize Channel Architecture**:
    - Move _all_ channels (Discord, Telegram, Signal) out of `src/` and into `extensions/`.
    - **Security Benefit**: Forces the Core to expose a strict, secure API for _all_ channels, preventing "privileged" core channels accessing internal state that extensions cannot.

### Phase 4: Long-Term audit (Ongoing)

1.  **Dependency Audit**:
    - Regular review of `pnpm.onlyBuiltDependencies`.
    - Minimize the list of packages allowed to run install scripts.

---

## 📝 Usage Simplification for End Users

To improve usability while maintaining security:

1.  **Unified "Doctor" Command**:
    - Enhance `autocrab doctor` to check for:
      - Correct Node.js version.
      - "OpenClaw" legacy config files (warn and offer to migrate).
      - Env var naming consistency.
2.  **One-Line Secure Install**:
    - Maintain the `npm install -g autocrab` simplicity but ensure it handles the `autocrab` vs `openclaw` conflict gracefully if an old install exists.
