import type { IncomingMessage, ServerResponse } from "node:http";
import { authorizeHttpGatewayConnect, type ResolvedGatewayAuth } from "../auth/index.js";
import type { AuthRateLimiter } from "../limits/auth.js";
import { sendGatewayAuthFailure } from "./common.js";
import { getBearerToken } from "./utils.js";

export async function authorizeGatewayBearerRequestOrReply(params: {
  req: IncomingMessage;
  res: ServerResponse;
  auth: ResolvedGatewayAuth;
  trustedProxies?: string[];
  allowRealIpFallback?: boolean;
  rateLimiter?: AuthRateLimiter;
}): Promise<boolean> {
  const token = getBearerToken(params.req);
  const authResult = await authorizeHttpGatewayConnect({
    auth: params.auth,
    connectAuth: token ? { token, password: token } : null,
    req: params.req,
    trustedProxies: params.trustedProxies,
    allowRealIpFallback: params.allowRealIpFallback,
    rateLimiter: params.rateLimiter,
  });
  if (!authResult.ok) {
    sendGatewayAuthFailure(params.res, authResult);
    return false;
  }
  return true;
}
