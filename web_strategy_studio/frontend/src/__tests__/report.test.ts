/**
 * Tests for report-related frontend components and utilities.
 */
import { describe, expect, it } from "vitest";

// ------------------------------------------------------------------
// API client utility tests
// ------------------------------------------------------------------

describe("resolveArtifactUrl", () => {
  it("returns undefined for null/empty input", async () => {
    const { resolveArtifactUrl } = await import("../api/client");
    expect(resolveArtifactUrl(null)).toBeUndefined();
    expect(resolveArtifactUrl("")).toBeUndefined();
    expect(resolveArtifactUrl("  ")).toBeUndefined();
  });

  it("passes through absolute URLs", async () => {
    const { resolveArtifactUrl } = await import("../api/client");
    expect(resolveArtifactUrl("https://example.com/report.html")).toBe(
      "https://example.com/report.html"
    );
    expect(resolveArtifactUrl("http://localhost:8080/api/v1/reports/run-1/report.html")).toBe(
      "http://localhost:8080/api/v1/reports/run-1/report.html"
    );
  });

  it("resolves relative paths with apiOrigin", async () => {
    const { resolveArtifactUrl } = await import("../api/client");
    // In test env, apiOrigin is "" so it uses window.location.origin
    const url = resolveArtifactUrl("/api/v1/reports/run-1/report.html");
    expect(url).toBeDefined();
    expect(url).toContain("/api/v1/reports/run-1/report.html");
  });

  it("rejects paths that don't start with /", async () => {
    const { resolveArtifactUrl } = await import("../api/client");
    expect(resolveArtifactUrl("relative/path.html")).toBeUndefined();
  });
});

describe("token management", () => {
  it("setToken and getToken work correctly", async () => {
    const { setToken, getToken } = await import("../api/client");
    setToken("test-token-123");
    expect(getToken()).toBe("test-token-123");
    setToken(null);
    expect(getToken()).toBeNull();
  });

  it("logout clears token", async () => {
    const { setToken, getToken, logout } = await import("../api/client");
    setToken("some-token");
    expect(getToken()).toBe("some-token");
    logout();
    expect(getToken()).toBeNull();
  });
});

// ------------------------------------------------------------------
// ReportViewer component import test
// ------------------------------------------------------------------

describe("ReportViewer component", () => {
  it("module exports a default component", async () => {
    const mod = await import("../components/ReportViewer");
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe("function");
  });
});

// ------------------------------------------------------------------
// ReportComparison component import test
// ------------------------------------------------------------------

describe("ReportComparison component", () => {
  it("module exports a default component", async () => {
    const mod = await import("../components/ReportComparison");
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe("function");
  });
});

// ------------------------------------------------------------------
// ReportPage component import test
// ------------------------------------------------------------------

describe("ReportPage component", () => {
  it("module exports a default component", async () => {
    const mod = await import("../pages/ReportPage");
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe("function");
  });
});

// ------------------------------------------------------------------
// MetricsComparison component import test
// ------------------------------------------------------------------

describe("MetricsComparison component", () => {
  it("module exports a named component", async () => {
    const mod = await import("../components/MetricsComparison");
    expect(mod.MetricsComparison).toBeDefined();
    expect(typeof mod.MetricsComparison).toBe("function");
  });
});
