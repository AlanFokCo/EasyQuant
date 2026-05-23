import { vi } from "vitest";

if (!("ResizeObserver" in globalThis)) {
  class ResizeObserver {
    observe(_target: Element, _options?: ResizeObserverOptions) {}
    unobserve(_target: Element) {}
    disconnect() {}
  }

  vi.stubGlobal("ResizeObserver", ResizeObserver);
}
