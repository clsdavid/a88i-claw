import { describe } from "vitest";
import { registerControlUiAndPairingSuite } from "./control-ui.suite.js";
import { installGatewayTestHooks } from "./test-hooks.js";

installGatewayTestHooks({ scope: "suite" });

describe("gateway server auth/connect", () => {
  registerControlUiAndPairingSuite();
});
