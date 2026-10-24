#!/usr/bin/env node
/**
 * Cross-platform launcher for electron-vite (Windows, macOS, Linux; x64 and arm64).
 *
 * `env -u ELECTRON_RUN_AS_NODE electron-vite dev` only works in a POSIX shell. Some terminals
 * (VS Code, Claude Code) export ELECTRON_RUN_AS_NODE=1, which makes Electron start as plain
 * Node and the app never opens. We drop it here and run electron-vite's own JS entry point
 * with the same Node, so no shell or `.cmd` shim is involved.
 */
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)
const pkg = require.resolve('electron-vite/package.json')
const bin = join(dirname(pkg), require(pkg).bin['electron-vite'])

const env = { ...process.env }
delete env.ELECTRON_RUN_AS_NODE

const child = spawn(process.execPath, [bin, ...process.argv.slice(2)], { stdio: 'inherit', env })
child.on('exit', (code, signal) => process.exit(signal ? 1 : (code ?? 0)))
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => child.kill(sig))
