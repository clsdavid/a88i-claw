import { describe, expect, it } from "vitest";
import { shortenText } from "./text-format.js";

describe("shortenText", () => {
  it("returns original text when it fits", () => {
    expect(shortenText("autocrab", 16)).toBe("autocrab");
  });

  it("truncates and appends ellipsis when over limit", () => {
    expect(shortenText("autocrab-status-output", 10)).toBe("autocrab-…");
  });

  it("counts multi-byte characters correctly", () => {
    expect(shortenText("hello🙂world", 7)).toBe("hello🙂…");
  });
});
