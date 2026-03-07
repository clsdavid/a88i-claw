import type { AutoCrabPluginApi } from "autocrab/plugin-sdk/googlechat";
import { emptyPluginConfigSchema } from "autocrab/plugin-sdk/googlechat";
import { googlechatDock, googlechatPlugin } from "./src/channel.js";
import { setGoogleChatRuntime } from "./src/runtime.js";

const plugin = {
  id: "googlechat",
  name: "Google Chat",
  description: "AutoCrab Google Chat channel plugin",
  configSchema: emptyPluginConfigSchema(),
  register(api: AutoCrabPluginApi) {
    setGoogleChatRuntime(api.runtime);
    api.registerChannel({ plugin: googlechatPlugin, dock: googlechatDock });
  },
};

export default plugin;
