import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Must match backend `EQ_STUDIO_UVICORN_PORT` (default 8080). Read in Node, not exposed to client bundle. */
const backendPort = process.env.EQ_STUDIO_UVICORN_PORT ?? "8080";
const backendTarget = `http://127.0.0.1:${backendPort}`;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backendTarget, changeOrigin: true },
      "/static": { target: backendTarget, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    passWithNoTests: true,
  },
});
