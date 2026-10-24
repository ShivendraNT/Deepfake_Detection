/**
 * Browser-only dev server for the renderer: `npm run dev:web` → http://localhost:5174
 * The console uses 5173. No Electron, no preload: `shared/api.ts` installs the mock bridge and
 * `VITE_SATYA_MOCK=1` forces it. Open `?view=stage` to play the three scenarios.
 */

import { resolve } from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  root: resolve(__dirname, 'renderer'),
  plugins: [react()],
  resolve: {
    alias: { '@': resolve(__dirname, 'renderer/src') },
  },
  define: {
    'import.meta.env.VITE_SATYA_MOCK': JSON.stringify('1'),
  },
  server: {
    port: 5174,
    strictPort: true,
    fs: { allow: [resolve(__dirname)] },
  },
  build: {
    outDir: resolve(__dirname, 'out/web'),
    emptyOutDir: true,
    rollupOptions: { input: resolve(__dirname, 'renderer/index.html') },
  },
})
