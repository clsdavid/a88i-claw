import { beforeEach, describe, expect, it, vi } from "vitest";
import { findBundledPluginSource, resolveBundledPluginSources } from "./bundled-sources.js";

const discoverAutoCrabPluginsMock = vi.fn();
const loadPluginManifestMock = vi.fn();

vi.mock("./discovery.js", () => ({
  discoverAutoCrabPlugins: (...args: unknown[]) => discoverAutoCrabPluginsMock(...args),
}));

vi.mock("./manifest.js", () => ({
  loadPluginManifest: (...args: unknown[]) => loadPluginManifestMock(...args),
}));

describe("bundled plugin sources", () => {
  beforeEach(() => {
    discoverAutoCrabPluginsMock.mockReset();
    loadPluginManifestMock.mockReset();
  });

  it("resolves bundled sources keyed by plugin id", () => {
    discoverAutoCrabPluginsMock.mockReturnValue({
      candidates: [
        {
          origin: "global",
          rootDir: "/global/feishu",
          packageName: "@autocrab/feishu",
          packageManifest: { install: { npmSpec: "@autocrab/feishu" } },
        },
        {
          origin: "bundled",
          rootDir: "/app/extensions/feishu",
          packageName: "@autocrab/feishu",
          packageManifest: { install: { npmSpec: "@autocrab/feishu" } },
        },
        {
          origin: "bundled",
          rootDir: "/app/extensions/feishu-dup",
          packageName: "@autocrab/feishu",
          packageManifest: { install: { npmSpec: "@autocrab/feishu" } },
        },
        {
          origin: "bundled",
          rootDir: "/app/extensions/msteams",
          packageName: "@autocrab/msteams",
          packageManifest: { install: { npmSpec: "@autocrab/msteams" } },
        },
      ],
      diagnostics: [],
    });

    loadPluginManifestMock.mockImplementation((rootDir: string) => {
      if (rootDir === "/app/extensions/feishu") {
        return { ok: true, manifest: { id: "feishu" } };
      }
      if (rootDir === "/app/extensions/msteams") {
        return { ok: true, manifest: { id: "msteams" } };
      }
      return {
        ok: false,
        error: "invalid manifest",
        manifestPath: `${rootDir}/autocrab.plugin.json`,
      };
    });

    const map = resolveBundledPluginSources({});

    expect(Array.from(map.keys())).toEqual(["feishu", "msteams"]);
    expect(map.get("feishu")).toEqual({
      pluginId: "feishu",
      localPath: "/app/extensions/feishu",
      npmSpec: "@autocrab/feishu",
    });
  });

  it("finds bundled source by npm spec", () => {
    discoverAutoCrabPluginsMock.mockReturnValue({
      candidates: [
        {
          origin: "bundled",
          rootDir: "/app/extensions/feishu",
          packageName: "@autocrab/feishu",
          packageManifest: { install: { npmSpec: "@autocrab/feishu" } },
        },
      ],
      diagnostics: [],
    });
    loadPluginManifestMock.mockReturnValue({ ok: true, manifest: { id: "feishu" } });

    const resolved = findBundledPluginSource({
      lookup: { kind: "npmSpec", value: "@autocrab/feishu" },
    });
    const missing = findBundledPluginSource({
      lookup: { kind: "npmSpec", value: "@autocrab/not-found" },
    });

    expect(resolved?.pluginId).toBe("feishu");
    expect(resolved?.localPath).toBe("/app/extensions/feishu");
    expect(missing).toBeUndefined();
  });

  it("finds bundled source by plugin id", () => {
    discoverAutoCrabPluginsMock.mockReturnValue({
      candidates: [
        {
          origin: "bundled",
          rootDir: "/app/extensions/diffs",
          packageName: "@autocrab/diffs",
          packageManifest: { install: { npmSpec: "@autocrab/diffs" } },
        },
      ],
      diagnostics: [],
    });
    loadPluginManifestMock.mockReturnValue({ ok: true, manifest: { id: "diffs" } });

    const resolved = findBundledPluginSource({
      lookup: { kind: "pluginId", value: "diffs" },
    });
    const missing = findBundledPluginSource({
      lookup: { kind: "pluginId", value: "not-found" },
    });

    expect(resolved?.pluginId).toBe("diffs");
    expect(resolved?.localPath).toBe("/app/extensions/diffs");
    expect(missing).toBeUndefined();
  });
});
