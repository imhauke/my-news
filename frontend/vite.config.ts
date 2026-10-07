/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // En producción Caddy hace lo mismo: /api/* → api:8000 sin el prefijo.
      "/api": { target: process.env.VITE_API_TARGET ?? "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"] },
});
