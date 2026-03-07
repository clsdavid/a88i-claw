// Narrow plugin-sdk surface for the bundled diffs plugin.
// Keep this list additive and scoped to symbols used under extensions/diffs.

export type { AutoCrabConfig } from "../config/config.js";
export { resolvePreferredAutoCrabTmpDir } from "../infra/tmp-autocrab-dir.js";
export type {
  AnyAgentTool,
  AutoCrabPluginApi,
  AutoCrabPluginConfigSchema,
  PluginLogger,
} from "../plugins/types.js";
