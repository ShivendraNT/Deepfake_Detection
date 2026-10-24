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
    assetsInclude: ['**/*.glb'],
    resolve: {
      alias: { '@': resolve(__dirname, 'renderer/src') },
    },
    server: { fs: { allow: [resolve(__dirname)] } },
    build: {
      outDir: resolve(__dirname, 'out/renderer'),
      emptyOutDir: true,
      // Never inline assets as data: URLs. The CSP (script-src 'self') refuses a data: script,
      // which silently broke the audio worklet (and so live capture) in built apps.
      assetsInlineLimit: 0,
      rollupOptions: { input: resolve(__dirname, 'renderer/index.html') },
    },
  },
})
