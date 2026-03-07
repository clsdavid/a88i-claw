import type { AutoCrabConfig } from "../../config/config.js";
import type { MsgContext } from "../templating.js";
import { buildCommandTestParams as buildBaseCommandTestParams } from "./commands.test-harness.js";

export function buildCommandTestParams(
  commandBody: string,
  cfg: AutoCrabConfig,
  ctxOverrides?: Partial<MsgContext>,
) {
  return buildBaseCommandTestParams(commandBody, cfg, ctxOverrides);
}
