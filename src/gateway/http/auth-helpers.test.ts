import type { IncomingMessage, ServerResponse } from "node:http";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ResolvedGatewayAuth } from "../auth/index.js";
import { authorizeGatewayBearerRequestOrReply } from "./auth-helpers.js";

vi.mock("./auth/index.js", () => ({
  authorizeHttpGatewayConnect: vi.fn(),
}));

vi.mock("./common.js", () => ({
  sendGatewayAuthFailure: vi.fn(),
}));

vi.mock("./utils.js", () => ({
  getBearerToken: vi.fn(),
}));

const { authorizeHttpGatewayConnect } = await import("../auth/index.js");
const { sendGatewayAuthFailure } = await import("./common.js");
const { getBearerToken } = await import("./utils.js");

describe("authorizeGatewayBearerRequestOrReply", () => {
  const bearerAuth = {
    mode: "token",
    token: "secret",
    password: undefined,
    allowTailscale: true,
  } satisfies ResolvedGatewayAuth;

  const makeAuthorizeParams = () => ({
    req: {} as IncomingMessage,
    res: {} as ServerResponse,
    auth: bearerAuth,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("disables tailscale header auth for HTTP bearer checks", async () => {
    vi.mocked(getBearerToken).mockReturnValue(undefined);
    vi.mocked(authorizeHttpGatewayConnect).mockResolvedValue({
      ok: false,
      reason: "token_missing",
    });

    const ok = await authorizeGatewayBearerRequestOrReply(makeAuthorizeParams());

    expect(ok).toBe(false);
    expect(vi.mocked(authorizeHttpGatewayConnect)).toHaveBeenCalledWith(
      expect.objectContaining({
        connectAuth: null,
      }),
    );
    expect(vi.mocked(sendGatewayAuthFailure)).toHaveBeenCalledTimes(1);
  });

  it("forwards bearer token and returns true on successful auth", async () => {
    vi.mocked(getBearerToken).mockReturnValue("abc");
    vi.mocked(authorizeHttpGatewayConnect).mockResolvedValue({ ok: true, method: "token" });

    const ok = await authorizeGatewayBearerRequestOrReply(makeAuthorizeParams());

    expect(ok).toBe(true);
    expect(vi.mocked(authorizeHttpGatewayConnect)).toHaveBeenCalledWith(
      expect.objectContaining({
        connectAuth: { token: "abc", password: "abc" },
      }),
    );
    expect(vi.mocked(sendGatewayAuthFailure)).not.toHaveBeenCalled();
  });
});
