import { describe } from "vitest";
import { registerAuthModesSuite } from "./modes.suite.js";
import { installGatewayTestHooks } from "./test-hooks.js";

installGatewayTestHooks({ scope: "suite" });

describe("gateway server auth/connect", () => {
  registerAuthModesSuite();
});
