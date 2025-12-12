const fs = require('fs')
const { execSync } = require('child_process')

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

// Vercel sometimes installs a truncated vite package (missing dist/node/cli.js),
// which breaks the standard `vite` bin. Workaround: fall back to npx to fetch
// a fresh copy and run the build.
const localCli = 'node_modules/vite/dist/node/cli.js'

console.log('[vercel-build] node', process.version)
console.log('[vercel-build] local vite cli exists:', exists(localCli))

if (exists(localCli)) {
  console.log('[vercel-build] Using local vite build')
  run('node node_modules/vite/bin/vite.js build')
} else {
  console.log('[vercel-build] Local vite is missing dist/node/cli.js — using npx vite@6.4.1 build')
  run('npx --yes vite@6.4.1 build')
}


