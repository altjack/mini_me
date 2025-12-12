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

function runCapture(cmd) {
  try {
    const stdout = execSync(cmd, { stdio: ['ignore', 'pipe', 'pipe'] })
    return { ok: true, stdout: String(stdout || '') }
  } catch (e) {
    return {
      ok: false,
      status: e && e.status,
      stdout: String((e && e.stdout) || ''),
      stderr: String((e && e.stderr) || ''),
      message: String(e),
    }
  }
}

function runOrDie(cmd, label) {
  const res = runCapture(cmd)
  if (res.ok) {
    if (res.stdout) process.stdout.write(res.stdout)
    return
  }
  console.log(`[vercel-build] ${label} FAILED (exit=${res.status ?? 'unknown'})`)
  if (res.stdout) console.log('[vercel-build] stdout:\n' + res.stdout)
  if (res.stderr) console.log('[vercel-build] stderr:\n' + res.stderr)
  console.log('[vercel-build] error:\n' + res.message)
  process.exit(res.status || 1)
}

// Vercel sometimes installs a truncated vite package (missing dist/node/cli.js),
// which breaks the standard `vite` bin. Workaround: fall back to npx to fetch
// a fresh copy and run the build.
const localCli = 'node_modules/vite/dist/node/cli.js'

console.log('[vercel-build] node', process.version)
console.log('[vercel-build] local vite cli exists:', exists(localCli))

if (exists(localCli)) {
  console.log('[vercel-build] Using local vite build')
  runOrDie('node node_modules/vite/bin/vite.js build --debug', 'local vite build')
} else {
  console.log('[vercel-build] Local vite is missing dist/node/cli.js — using npx vite@6.4.1 build')
  // --prefer-online avoids reusing a potentially bad cached package
  runOrDie('npx --yes --prefer-online vite@6.4.1 build --debug', 'npx vite@6.4.1 build')
}


