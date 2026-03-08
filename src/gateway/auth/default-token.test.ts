import { describe } from "vitest";
import { registerDefaultAuthTokenSuite } from "./default-token.suite.js";
import { installGatewayTestHooks } from "./test-hooks.js";

installGatewayTestHooks({ scope: "suite" });

describe("gateway server auth/connect", () => {
  registerDefaultAuthTokenSuite();
});
