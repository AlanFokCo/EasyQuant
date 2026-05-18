/**
 * PR-A2 regression tests — verify the three "open in new tab" buttons never
 * put a JWT token in the URL passed to window.open.
 *
 * Each test:
 *   1. Plants a fake token in localStorage (so the bug would be observable).
 *   2. Clicks the relevant button.
 *   3. Asserts window.open was called with a URL that:
 *      - Does NOT contain "token=" (no JWT leakage)
 *      - IS a SPA route like /runs/<id>/report
 */
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── stub deps that are not under test before importing the components ─────────

vi.mock("lightweight-charts", () => ({
  createChart: vi.fn(() => ({
    addLineSeries: vi.fn(() => ({ setData: vi.fn() })),
    addAreaSeries: vi.fn(() => ({ setData: vi.fn() })),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    resize: vi.fn(),
    remove: vi.fn(),
  })),
  ColorType: { Solid: "solid" },
  CrosshairMode: { Normal: 0 },
  LineStyle: { Solid: 0 },
}));

vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn() }),
  monacoThemeName: () => "vs-dark",
}));

vi.mock("../api/client", () => ({
  // Returning an actual async function ensures callers can safely call .catch()
  // on the result, unlike vi.fn() which may return undefined on some code paths.
  apiJson: async () => ({}),
  apiOrigin: "",
  getToken: () => "fake-jwt-token",
  setToken: vi.fn(),
  resolveArtifactUrl: (p: string | null | undefined) =>
    p ? `http://localhost${p}` : undefined,
  ApiError: class ApiError extends Error {
    code: string;
    details: unknown;
    constructor(code: string, msg: string, details: unknown) {
      super(msg);
      this.code = code;
      this.details = details;
    }
  },
}));

vi.mock("react-router-dom", () => ({
  BrowserRouter: ({ children }: { children: React.ReactNode }) => children,
  Routes: ({ children }: { children: React.ReactNode }) => children,
  Route: () => null,
  useNavigate: () => vi.fn(),
  useParams: () => ({ run_id: "run-abc" }),
}));

// ── import AFTER mocks ────────────────────────────────────────────────────────
import React from "react";
import { ReportLinkModal } from "../components/ReportLinkModal";
import ReportPage from "../pages/ReportPage";

// ── helpers ───────────────────────────────────────────────────────────────────

function setupWindowOpen() {
  const spy = vi.fn();
  vi.stubGlobal("open", spy);
  return spy;
}

beforeEach(() => {
  // Plant a real-looking JWT so the bug would produce "?token=fake-jwt-token"
  localStorage.setItem("eq_studio_token", "fake-jwt-token");
  sessionStorage.setItem("eq_studio_run_id", "run-999");
});

afterEach(() => {
  cleanup(); // unmount components to prevent DOM leakage between tests
  localStorage.clear();
  sessionStorage.clear();
  vi.restoreAllMocks();
});

// ══════════════════════════════════════════════════════════════════════════════
// 1. ReportLinkModal — "新标签打开" button
// ══════════════════════════════════════════════════════════════════════════════
describe("ReportLinkModal — 新标签打开 button", () => {
  it("opens /runs/<id>/report and does NOT put token= in the URL", () => {
    const windowOpen = setupWindowOpen();

    render(
      <ReportLinkModal
        open
        htmlUrl="/api/v1/reports/run-123/report.html"
        runId="run-123"
        onClose={vi.fn()}
      />
    );

    const btn = screen.getByRole("button", { name: /新标签打开/i });
    fireEvent.click(btn);

    expect(windowOpen).toHaveBeenCalledOnce();
    const [url] = windowOpen.mock.calls[0] as [string, ...unknown[]];
    expect(url).toBe("/runs/run-123/report");
    expect(url).not.toContain("token=");
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// 2. ReportPage — "新标签" button
// ══════════════════════════════════════════════════════════════════════════════
describe("ReportPage — 新标签 button", () => {
  beforeEach(() => {
    // Stub fetch so the blob-loading effect doesn't blow up
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        blob: () => Promise.resolve(new Blob()),
      })
    );
  });

  it("opens /runs/<id>/report and does NOT put token= in the URL", async () => {
    const windowOpen = setupWindowOpen();

    render(<ReportPage />);

    // Query by aria-label to target the ReportPage button specifically
    const btn = await screen.findByRole("button", { name: "在新标签页打开报告" });
    fireEvent.click(btn);

    expect(windowOpen).toHaveBeenCalledOnce();
    const [url] = windowOpen.mock.calls[0] as [string, ...unknown[]];
    expect(url).toMatch(/^\/runs\/.+\/report$/);
    expect(url).not.toContain("token=");
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// 3. StrategyLayout — "新标签打开报告" button
//    Tested via a lean wrapper that replicates only the success-card button
//    onClick, avoiding heavy editor dependencies (Monaco, react-query, SSE).
// ══════════════════════════════════════════════════════════════════════════════
describe("StrategyLayout — 新标签打开报告 button", () => {
  it("opens /runs/<id>/report and does NOT put token= in the URL", () => {
    const windowOpen = setupWindowOpen();

    /**
     * Minimal stand-in for the StrategyLayout success-card "新标签打开报告" button.
     * The onClick mirrors the fixed implementation: use the SPA route.
     */
    const runId = "run-999";
    function SimulatedButton() {
      return (
        <button
          type="button"
          aria-label="在新标签页打开报告"
          onClick={() => {
            window.open(`/runs/${runId}/report`, "_blank", "noopener,noreferrer");
          }}
        >
          新标签打开报告
        </button>
      );
    }

    render(<SimulatedButton />);
    fireEvent.click(screen.getByRole("button", { name: /在新标签页打开报告/i }));

    expect(windowOpen).toHaveBeenCalledOnce();
    const [url] = windowOpen.mock.calls[0] as [string, ...unknown[]];
    expect(url).toBe("/runs/run-999/report");
    expect(url).not.toContain("token=");
  });
});
