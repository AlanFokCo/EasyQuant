/**
 * Tests for the cn utility (clsx + tailwind-merge).
 */
import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn utility", () => {
  it("merges simple class names", () => {
    expect(cn("px-4", "py-2")).toBe("px-4 py-2");
  });

  it("resolves conflicting Tailwind classes (last wins)", () => {
    expect(cn("px-4", "px-8")).toBe("px-8");
  });

  it("handles conditional classes", () => {
    const active = true;
    expect(cn("base", active && "active")).toBe("base active");
  });

  it("handles falsy values", () => {
    expect(cn("base", false, null, undefined, "")).toBe("base");
  });

  it("merges bg-color conflicts correctly", () => {
    expect(cn("bg-red-500", "bg-blue-500")).toBe("bg-blue-500");
  });
});
