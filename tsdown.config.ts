import { defineConfig } from "tsdown";

const env = {
  NODE_ENV: "production",
};

const baseConfig = {
  env,
  fixedExtension: false,
  platform: "node" as const,
  // Force bundling of workspace packages to avoid external module resolution issues at runtime
  noExternal: [/^@autocrab\//],
};

const pluginSdkEntrypoints = [
  "index",
  "core",
  "compat",
  "telegram",
  "discord",
  "slack",
  "signal",
  "imessage",
  "whatsapp",
  "line",
  "msteams",
  "acpx",
  "bluebubbles",
  "copilot-proxy",
  "device-pair",
  "diagnostics-otel",
  "diffs",
  "feishu",
  "google-gemini-cli-auth",
  "googlechat",
  "irc",
  "llm-task",
  "lobster",
  "matrix",
  "mattermost",
  "memory-core",
  "memory-lancedb",
  "minimax-portal-auth",
  "nextcloud-talk",
  "nostr",
  "open-prose",
  "phone-control",
  "qwen-portal-auth",
  "synology-chat",
  "talk-voice",
  "test-utils",
  "thread-ownership",
  "tlon",
  "twitch",
  "voice-call",
  "zalo",
  "zalouser",
  "account-id",
  "keyed-async-queue",
] as const;

export default defineConfig([
  {
    entry: "src/index.ts",
    ...baseConfig,
  },
  {
    entry: "src/entry.ts",
    ...baseConfig,
  },
  {
    // Ensure this module is bundled as an entry so legacy CLI shims can resolve its exports.
    entry: "src/cli/daemon-cli.ts",
    ...baseConfig,
  },
  {
    entry: "src/infra/warning-filter.ts",
    ...baseConfig,
  },
  {
    // Keep sync lazy-runtime channel modules as concrete dist files.
    entry: {
      "channels/plugins/agent-tools/whatsapp-login":
        "src/channels/plugins/agent-tools/whatsapp-login.ts",
      "channels/plugins/actions/discord": "src/channels/plugins/actions/discord.ts",
      "channels/plugins/actions/signal": "src/channels/plugins/actions/signal.ts",
      "channels/plugins/actions/telegram": "src/channels/plugins/actions/telegram.ts",
      "telegram/audit": "extensions/telegram/src/audit.ts",
      "telegram/token": "extensions/telegram/src/token.ts",
      "line/accounts": "src/line/accounts.ts",
      "line/send": "src/line/send.ts",
      "line/template-messages": "src/line/template-messages.ts",
    },
    ...baseConfig,
  },
  ...pluginSdkEntrypoints.map((entry) => ({
    entry: `src/plugin-sdk/${entry}.ts`,
    outDir: "dist/plugin-sdk",
    ...baseConfig,
  })),
  {
    entry: "src/extensionAPI.ts",
    ...baseConfig,
  },
  {
    entry: ["src/hooks/bundled/*/handler.ts", "src/hooks/llm-slug-generator.ts"],
    ...baseConfig,
  },
]);
