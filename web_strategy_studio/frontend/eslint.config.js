// @ts-check
import js from "@eslint/js";
import tsEslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tsEslint.config(
  // Ignore build output and deps
  { ignores: ["dist/**", "node_modules/**"] },

  // Base JS recommended rules
  js.configs.recommended,

  // TypeScript recommended rules (includes parser config)
  ...tsEslint.configs.recommended,

  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // React Hooks — catches dependency-array bugs (caught Phase 2 B2)
      ...reactHooks.configs.recommended.rules,

      // React Refresh — warn about non-component exports in component files
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],

      // Relax a few noisy TS rules for gradual adoption
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },

  // Lightweight Charts v4 requires `as any` casts for series options —
  // its types are stricter than the actual runtime API accepts.
  {
    files: ["src/components/ReportViewer.tsx", "src/components/MetricsComparison.tsx"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
