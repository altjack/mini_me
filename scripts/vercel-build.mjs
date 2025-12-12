import fs from 'node:fs'
import { execSync } from 'node:child_process'

function exists(p) {
  try {
    fs.accessSync(p, fs.constants.R_OK)
    return true
  } catch {
    return false
  }
}

function run(cmd) {
  execSync(cmd, { stdio: 'inherit' })
}

// If Vercel (or its builder) drops node_modules/vite/dist, Vite's own bin breaks.
// Workaround: fall back to npx which fetches a fresh copy in its own cache.
const localCli = 'node_modules/vite/dist/node/cli.js'

if (exists(localCli)) {
  console.log('[vercel-build] Using local vite from node_modules')
  run('node node_modules/vite/bin/vite.js build')
} else {
  console.log('[vercel-build] Local vite is missing dist/node/cli.js, falling back to npx vite@7.2.7')
  run('npx --yes vite@7.2.7 build')
}


