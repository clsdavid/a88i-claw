import type { AnyAgentTool, AutoCrabPluginApi } from "autocrab/plugin-sdk/llm-task";
import { createLlmTaskTool } from "./src/llm-task-tool.js";

export default function register(api: AutoCrabPluginApi) {
  api.registerTool(createLlmTaskTool(api) as unknown as AnyAgentTool, { optional: true });
}
