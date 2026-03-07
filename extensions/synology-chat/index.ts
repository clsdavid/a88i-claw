import type { AutoCrabPluginApi } from "autocrab/plugin-sdk/synology-chat";
import { emptyPluginConfigSchema } from "autocrab/plugin-sdk/synology-chat";
import { createSynologyChatPlugin } from "./src/channel.js";
import { setSynologyRuntime } from "./src/runtime.js";

const plugin = {
  id: "synology-chat",
  name: "Synology Chat",
  description: "Native Synology Chat channel plugin for AutoCrab",
  configSchema: emptyPluginConfigSchema(),
  register(api: AutoCrabPluginApi) {
    setSynologyRuntime(api.runtime);
    api.registerChannel({ plugin: createSynologyChatPlugin() });
  },
};

export default plugin;
