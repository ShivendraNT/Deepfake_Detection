/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend serves the built dashboard at /lab (index.html fallback for client routes)
// from src/satyapan/forensics/ui, so the build is committed and judges need no Node.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const api = env.VITE_API || "http://127.0.0.1:8010";
  return {
    base: "/lab/",
    plugins: [react()],
    build: {
      outDir: "../src/satyapan/forensics/ui",
      emptyOutDir: true,
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ["react", "react-dom", "react-router-dom"],
            charts: ["recharts"],
            graph: ["@xyflow/react"],
            motion: ["framer-motion"],
          },
        },
      },
    },
    server: {
      host: "127.0.0.1",
      port: 5175,
      strictPort: true,
      proxy: {
        "/lab/api": { target: api, changeOrigin: true },
      },
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.ts"],
    },
  };
});
