import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { withEnv } from "../test-utils/env.js";
import { resolveAutoCrabAgentDir } from "./agent-paths.js";

describe("resolveAutoCrabAgentDir", () => {
  const withTempStateDir = async (run: (stateDir: string) => void) => {
    const stateDir = await fs.mkdtemp(path.join(os.tmpdir(), "autocrab-agent-"));
    try {
      run(stateDir);
    } finally {
      await fs.rm(stateDir, { recursive: true, force: true });
    }
  };

  it("defaults to the multi-agent path when no overrides are set", async () => {
    await withTempStateDir((stateDir) => {
      withEnv(
        {
          AUTOCRAB_STATE_DIR: stateDir,
          AUTOCRAB_AGENT_DIR: undefined,
          PI_CODING_AGENT_DIR: undefined,
        },
        () => {
          const resolved = resolveAutoCrabAgentDir();
          expect(resolved).toBe(path.join(stateDir, "agents", "main", "agent"));
        },
      );
    });
  });

  it("honors AUTOCRAB_AGENT_DIR overrides", async () => {
    await withTempStateDir((stateDir) => {
      const override = path.join(stateDir, "agent");
      withEnv(
        {
          AUTOCRAB_STATE_DIR: undefined,
          AUTOCRAB_AGENT_DIR: override,
          PI_CODING_AGENT_DIR: undefined,
        },
        () => {
          const resolved = resolveAutoCrabAgentDir();
          expect(resolved).toBe(path.resolve(override));
        },
      );
    });
  });

  it("honors PI_CODING_AGENT_DIR when AUTOCRAB_AGENT_DIR is unset", async () => {
    await withTempStateDir((stateDir) => {
      const override = path.join(stateDir, "pi-agent");
      withEnv(
        {
          AUTOCRAB_STATE_DIR: undefined,
          AUTOCRAB_AGENT_DIR: undefined,
          PI_CODING_AGENT_DIR: override,
        },
        () => {
          const resolved = resolveAutoCrabAgentDir();
          expect(resolved).toBe(path.resolve(override));
        },
      );
    });
  });

  it("prefers AUTOCRAB_AGENT_DIR over PI_CODING_AGENT_DIR when both are set", async () => {
    await withTempStateDir((stateDir) => {
      const primaryOverride = path.join(stateDir, "primary-agent");
      const fallbackOverride = path.join(stateDir, "fallback-agent");
      withEnv(
        {
          AUTOCRAB_STATE_DIR: undefined,
          AUTOCRAB_AGENT_DIR: primaryOverride,
          PI_CODING_AGENT_DIR: fallbackOverride,
        },
        () => {
          const resolved = resolveAutoCrabAgentDir();
          expect(resolved).toBe(path.resolve(primaryOverride));
        },
      );
    });
  });
});
