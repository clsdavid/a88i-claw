# Authentication Rate Limiting

The Gateway implements strict rate limiting for authentication attempts to prevent brute-force attacks. This logic is enforced in `src/gateway/limits/auth.ts`.

## Configuration

The rate limiter uses a sliding window algorithm with the following default parameters:

- **Max Attempts**: 10 failed attempts allowed.
- **Window**: 60 seconds (1 minute).
- **Lockout**: 300 seconds (5 minutes) after exceeding the limit.
- **Scope**: Limits are tracked per IP address and authentication scope (e.g., `shared-secret` vs `device-token`).

## Trusted Proxy & IP Spoofing Risks

When running the Gateway behind a reverse proxy (e.g., Nginx, Cloudflare, load balancer), the Gateway sees the proxy's IP address rather than the client's real IP. To fix this, you may configure the **Trusted Proxy** mode.

**⚠️ WARNING: Security Risk**

If Trusted Proxy mode is enabled, the Gateway trusts headers like `X-Forwarded-For` or `X-Real-IP` to determine the client's IP address.

- **Misconfiguration Risk**: If your Gateway is directly accessible from the internet (bypassing the proxy) while Trusted Proxy mode is enabled, an attacker can spoof these headers to bypass rate limits or IP allowlists.
- **Mitigation**: Ensure that when Trusted Proxy mode is active, the Gateway binds **only** to the interface connected to the proxy (e.g., `127.0.0.1` or a private internal IP), or strictly firewall port 18789 to allow only the proxy's IP.

Always verify your network topology before enabling trust for these headers.
