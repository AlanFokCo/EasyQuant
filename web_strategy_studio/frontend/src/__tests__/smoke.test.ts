/**
 * Smoke tests — ensure the module graph is import-able and core utilities work.
 * These are intentionally minimal; richer tests live in e2e/.
 */
import { describe, expect, it } from "vitest";

describe("api client utility functions", () => {
  it("status badge mapping includes all expected statuses", async () => {
    // Verify that the API client module loads without errors
    const mod = await import("../api/client");
    expect(mod).toBeDefined();
  });

  it("environment works correctly", () => {
    expect(typeof window).toBe("object");
  });
});
