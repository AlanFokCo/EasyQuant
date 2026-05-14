export const apiOrigin = import.meta.env.VITE_API_ORIGIN || "";
export const apiV1 = `${apiOrigin}/api/v1`;

/** Absolute URL for opening / embedding reports (iframe, window.open). */
export function resolveArtifactUrl(path: string | undefined | null): string | undefined {
  if (!path?.trim()) return undefined;
  const p = path.trim();
  if (p.startsWith("http://") || p.startsWith("https://")) return p;
  if (!p.startsWith("/")) return undefined;
  const base = apiOrigin.replace(/\/$/, "");
  if (base) return `${base}${p}`;
  if (typeof window !== "undefined") return `${window.location.origin}${p}`;
  return p;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiOrigin}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
