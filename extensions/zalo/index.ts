import type { AutoCrabPluginApi } from "autocrab/plugin-sdk/zalo";
import { emptyPluginConfigSchema } from "autocrab/plugin-sdk/zalo";
import { zaloDock, zaloPlugin } from "./src/channel.js";
import { setZaloRuntime } from "./src/runtime.js";

const plugin = {
  id: "zalo",
  name: "Zalo",
  description: "Zalo channel plugin (Bot API)",
  configSchema: emptyPluginConfigSchema(),
  register(api: AutoCrabPluginApi) {
    setZaloRuntime(api.runtime);
    api.registerChannel({ plugin: zaloPlugin, dock: zaloDock });
  },
};

export default plugin;
