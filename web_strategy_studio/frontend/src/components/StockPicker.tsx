/**
 * StockPicker — searchable dropdown for A-share stocks.
 * Uses /api/v1/symbols/search (local eqlib_symbols.json) for type-ahead.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { apiJson } from "../api/client";

type Symbol = { code: string; name: string };

interface Props {
  value: string;
  onChange: (code: string) => void;
  placeholder?: string;
}

export function StockPicker({ value, onChange, placeholder }: Props) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<Symbol[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Sync external value changes
  useEffect(() => {
    setQuery(value);
  }, [value]);

  const doSearch = useCallback((q: string) => {
    if (!q || q.length < 1) {
      setResults([]);
      return;
    }
    apiJson<Symbol[]>(`/api/v1/symbols/search?q=${encodeURIComponent(q)}&limit=15`)
      .then(setResults)
      .catch(() => setResults([]));
  }, []);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setQuery(v);
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(v), 200);
  };

  const select = (code: string) => {
    setQuery(code);
    onChange(code);
    setOpen(false);
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <input
        value={query}
        onChange={onInputChange}
        onFocus={() => setOpen(true)}
        placeholder={placeholder || "搜索股票代码/名称"}
        style={{
          width: "100%",
          marginTop: 2,
          padding: 4,
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-sm)",
          color: "var(--text)",
          fontSize: 12,
        }}
      />
      {open && results.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 50,
            maxHeight: 200,
            overflowY: "auto",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            marginTop: 2,
          }}
        >
          {results.map((s) => (
            <div
              key={s.code}
              role="option"
              aria-selected={s.code === value}
              style={{
                padding: "4px 8px",
                cursor: "pointer",
                fontSize: 12,
                color: s.code === value ? "var(--primary)" : "var(--text)",
                background: s.code === value ? "var(--bg-tertiary)" : "transparent",
              }}
              onMouseDown={() => select(s.code)}
            >
              <span style={{ fontWeight: 600, marginRight: 6 }}>{s.code}</span>
              <span style={{ color: "var(--text-dim)" }}>{s.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
