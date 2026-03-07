import type {
  AnyAgentTool,
  AutoCrabPluginApi,
  AutoCrabPluginToolFactory,
} from "autocrab/plugin-sdk/lobster";
import { createLobsterTool } from "./src/lobster-tool.js";

export default function register(api: AutoCrabPluginApi) {
  api.registerTool(
    ((ctx) => {
      if (ctx.sandboxed) {
        return null;
      }
      return createLobsterTool(api) as AnyAgentTool;
    }) as AutoCrabPluginToolFactory,
    { optional: true },
  );
}
