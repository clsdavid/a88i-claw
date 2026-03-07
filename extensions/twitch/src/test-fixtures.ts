import type { AutoCrabConfig } from "autocrab/plugin-sdk/twitch";
import { afterEach, beforeEach, vi } from "vitest";

export const BASE_TWITCH_TEST_ACCOUNT = {
  username: "testbot",
  clientId: "test-client-id",
  channel: "#testchannel",
};

export function makeTwitchTestConfig(account: Record<string, unknown>): AutoCrabConfig {
  return {
    channels: {
      twitch: {
        accounts: {
          default: account,
        },
      },
    },
  } as unknown as AutoCrabConfig;
}

export function installTwitchTestHooks() {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });
}
