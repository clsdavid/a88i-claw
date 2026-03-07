import { vi } from "vitest";
import { installChromeUserDataDirHooks } from "./chrome-user-data-dir.test-harness.js";

const chromeUserDataDir = { dir: "/tmp/autocrab" };
installChromeUserDataDirHooks(chromeUserDataDir);

vi.mock("./chrome.js", () => ({
  isChromeCdpReady: vi.fn(async () => true),
  isChromeReachable: vi.fn(async () => true),
  launchAutoCrabChrome: vi.fn(async () => {
    throw new Error("unexpected launch");
  }),
  resolveAutoCrabUserDataDir: vi.fn(() => chromeUserDataDir.dir),
  stopAutoCrabChrome: vi.fn(async () => {}),
}));
