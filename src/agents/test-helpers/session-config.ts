import type { AutoCrabConfig } from "../../config/config.js";

export function createPerSenderSessionConfig(
  overrides: Partial<NonNullable<AutoCrabConfig["session"]>> = {},
): NonNullable<AutoCrabConfig["session"]> {
  return {
    mainKey: "main",
    scope: "per-sender",
    ...overrides,
  };
}
