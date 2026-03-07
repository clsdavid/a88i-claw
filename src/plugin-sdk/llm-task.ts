// Narrow plugin-sdk surface for the bundled llm-task plugin.
// Keep this list additive and scoped to symbols used under extensions/llm-task.

export { resolvePreferredAutoCrabTmpDir } from "../infra/tmp-autocrab-dir.js";
export type { AnyAgentTool, AutoCrabPluginApi } from "../plugins/types.js";
