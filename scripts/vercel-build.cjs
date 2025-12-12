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

function rmrf(p) {
  try {
    fs.rmSync(p, { recursive: true, force: true })
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
  console.log('[vercel-build] Local vite is missing dist/node/cli.js — removing local vite and running npm exec --package=vite@6.4.1')

  // Important: `npx vite@...` prefers the local binary if present, which is exactly what we need to avoid.
  // So we delete the broken local vite and use `npm exec --package` to fetch a clean copy.
  rmrf('node_modules/vite')
  rmrf('node_modules/.bin/vite')
  rmrf('node_modules/.bin/vite.cmd')
  rmrf('node_modules/.bin/vite.ps1')

  // Use a separate npm cache in /tmp to reduce flakiness across builds.
  runOrDie(
    'NPM_CONFIG_CACHE=/tmp/npm-cache npm exec --yes --package=vite@6.4.1 -- vite build --debug',
    'npm exec vite@6.4.1 build'
  )
}


