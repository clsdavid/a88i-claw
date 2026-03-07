import path from "node:path";
import { describe, expect, it } from "vitest";
import { formatCliCommand } from "./command-format.js";
import { applyCliProfileEnv, parseCliProfileArgs } from "./profile.js";

describe("parseCliProfileArgs", () => {
  it("leaves gateway --dev for subcommands", () => {
    const res = parseCliProfileArgs([
      "node",
      "autocrab",
      "gateway",
      "--dev",
      "--allow-unconfigured",
    ]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBeNull();
    expect(res.argv).toEqual(["node", "autocrab", "gateway", "--dev", "--allow-unconfigured"]);
  });

  it("still accepts global --dev before subcommand", () => {
    const res = parseCliProfileArgs(["node", "autocrab", "--dev", "gateway"]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBe("dev");
    expect(res.argv).toEqual(["node", "autocrab", "gateway"]);
  });

  it("parses --profile value and strips it", () => {
    const res = parseCliProfileArgs(["node", "autocrab", "--profile", "work", "status"]);
    if (!res.ok) {
      throw new Error(res.error);
    }
    expect(res.profile).toBe("work");
    expect(res.argv).toEqual(["node", "autocrab", "status"]);
  });

  it("rejects missing profile value", () => {
    const res = parseCliProfileArgs(["node", "autocrab", "--profile"]);
    expect(res.ok).toBe(false);
  });

  it.each([
    ["--dev first", ["node", "autocrab", "--dev", "--profile", "work", "status"]],
    ["--profile first", ["node", "autocrab", "--profile", "work", "--dev", "status"]],
  ])("rejects combining --dev with --profile (%s)", (_name, argv) => {
    const res = parseCliProfileArgs(argv);
    expect(res.ok).toBe(false);
  });
});

describe("applyCliProfileEnv", () => {
  it("fills env defaults for dev profile", () => {
    const env: Record<string, string | undefined> = {};
    applyCliProfileEnv({
      profile: "dev",
      env,
      homedir: () => "/home/peter",
    });
    const expectedStateDir = path.join(path.resolve("/home/peter"), ".autocrab-dev");
    expect(env.AUTOCRAB_PROFILE).toBe("dev");
    expect(env.AUTOCRAB_STATE_DIR).toBe(expectedStateDir);
    expect(env.AUTOCRAB_CONFIG_PATH).toBe(path.join(expectedStateDir, "autocrab.json"));
    expect(env.AUTOCRAB_GATEWAY_PORT).toBe("19001");
  });

  it("does not override explicit env values", () => {
    const env: Record<string, string | undefined> = {
      AUTOCRAB_STATE_DIR: "/custom",
      AUTOCRAB_GATEWAY_PORT: "19099",
    };
    applyCliProfileEnv({
      profile: "dev",
      env,
      homedir: () => "/home/peter",
    });
    expect(env.AUTOCRAB_STATE_DIR).toBe("/custom");
    expect(env.AUTOCRAB_GATEWAY_PORT).toBe("19099");
    expect(env.AUTOCRAB_CONFIG_PATH).toBe(path.join("/custom", "autocrab.json"));
  });

  it("uses AUTOCRAB_HOME when deriving profile state dir", () => {
    const env: Record<string, string | undefined> = {
      AUTOCRAB_HOME: "/srv/autocrab-home",
      HOME: "/home/other",
    };
    applyCliProfileEnv({
      profile: "work",
      env,
      homedir: () => "/home/fallback",
    });

    const resolvedHome = path.resolve("/srv/autocrab-home");
    expect(env.AUTOCRAB_STATE_DIR).toBe(path.join(resolvedHome, ".autocrab-work"));
    expect(env.AUTOCRAB_CONFIG_PATH).toBe(
      path.join(resolvedHome, ".autocrab-work", "autocrab.json"),
    );
  });
});

describe("formatCliCommand", () => {
  it.each([
    {
      name: "no profile is set",
      cmd: "autocrab doctor --fix",
      env: {},
      expected: "autocrab doctor --fix",
    },
    {
      name: "profile is default",
      cmd: "autocrab doctor --fix",
      env: { AUTOCRAB_PROFILE: "default" },
      expected: "autocrab doctor --fix",
    },
    {
      name: "profile is Default (case-insensitive)",
      cmd: "autocrab doctor --fix",
      env: { AUTOCRAB_PROFILE: "Default" },
      expected: "autocrab doctor --fix",
    },
    {
      name: "profile is invalid",
      cmd: "autocrab doctor --fix",
      env: { AUTOCRAB_PROFILE: "bad profile" },
      expected: "autocrab doctor --fix",
    },
    {
      name: "--profile is already present",
      cmd: "autocrab --profile work doctor --fix",
      env: { AUTOCRAB_PROFILE: "work" },
      expected: "autocrab --profile work doctor --fix",
    },
    {
      name: "--dev is already present",
      cmd: "autocrab --dev doctor",
      env: { AUTOCRAB_PROFILE: "dev" },
      expected: "autocrab --dev doctor",
    },
  ])("returns command unchanged when $name", ({ cmd, env, expected }) => {
    expect(formatCliCommand(cmd, env)).toBe(expected);
  });

  it("inserts --profile flag when profile is set", () => {
    expect(formatCliCommand("autocrab doctor --fix", { AUTOCRAB_PROFILE: "work" })).toBe(
      "autocrab --profile work doctor --fix",
    );
  });

  it("trims whitespace from profile", () => {
    expect(formatCliCommand("autocrab doctor --fix", { AUTOCRAB_PROFILE: "  jbautocrab  " })).toBe(
      "autocrab --profile jbautocrab doctor --fix",
    );
  });

  it("handles command with no args after autocrab", () => {
    expect(formatCliCommand("autocrab", { AUTOCRAB_PROFILE: "test" })).toBe(
      "autocrab --profile test",
    );
  });

  it("handles pnpm wrapper", () => {
    expect(formatCliCommand("pnpm autocrab doctor", { AUTOCRAB_PROFILE: "work" })).toBe(
      "pnpm autocrab --profile work doctor",
    );
  });
});
