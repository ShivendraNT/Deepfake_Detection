import { resolve } from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: 'out/main',
      lib: { entry: resolve(__dirname, 'main/index.ts') },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: 'out/preload',
      lib: { entry: resolve(__dirname, 'preload/index.ts') },
    },
  },
  renderer: {
    root: resolve(__dirname, 'renderer'),
    plugins: [react()],
    resolve: {
      alias: { '@': resolve(__dirname, 'renderer/src') },
    },
    server: { fs: { allow: [resolve(__dirname)] } },
    build: {
      outDir: resolve(__dirname, 'out/renderer'),
      emptyOutDir: true,
      rollupOptions: { input: resolve(__dirname, 'renderer/index.html') },
    },
  },
})
