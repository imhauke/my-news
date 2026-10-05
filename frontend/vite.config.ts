/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // `process.env` alone never sees `.env`/`.env.local` — those are loaded for
  // client code (`import.meta.env`) automatically, but config code like this
  // proxy target has to ask explicitly, or it silently falls back to :8000
  // every time, which on this machine is BePresent's backend, not ours.
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      proxy: {
        // In production Caddy does the same: /api/* → api:8000 without the prefix.
        "/api": { target: env.VITE_API_TARGET ?? "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") },
      },
    },
    test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"] },
  };
});
