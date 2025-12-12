import fs from 'node:fs'
import { execSync } from 'node:child_process'

function log(cmd) {
  try {
    const out = execSync(cmd, { stdio: ['ignore', 'pipe', 'pipe'] }).toString()
    process.stdout.write(out.endsWith('\n') ? out : out + '\n')
  } catch (e) {
    process.stdout.write(`[vercel-prebuild] command failed: ${cmd}\n`)
    process.stdout.write(String(e?.stdout ?? ''))
    process.stderr.write(String(e?.stderr ?? ''))
  }
}

function exists(p) {
  try {
    fs.accessSync(p, fs.constants.R_OK)
    return true
  } catch {
    return false
  }
}

console.log('[vercel-prebuild] node:', process.version)
log('npm -v')

// Diagnostics: show resolved vite version (if installed)
try {
  // eslint-disable-next-line import/no-extraneous-dependencies
  const vitePkg = JSON.parse(fs.readFileSync('node_modules/vite/package.json', 'utf8'))
  console.log('[vercel-prebuild] vite version:', vitePkg.version)
} catch (e) {
  console.log('[vercel-prebuild] vite package.json not readable yet:', String(e))
}

const cliPath = 'node_modules/vite/dist/node/cli.js'
if (exists(cliPath)) {
  console.log('[vercel-prebuild] OK: found', cliPath)
  process.exit(0)
}

console.log('[vercel-prebuild] MISSING:', cliPath)
console.log('[vercel-prebuild] Listing node_modules/vite/dist/node (if present):')
log('ls -la node_modules/vite/dist/node || true')
console.log('[vercel-prebuild] Listing node_modules/vite/dist (if present):')
log('ls -la node_modules/vite/dist || true')
console.log('[vercel-prebuild] Listing node_modules/vite (top-level):')
log('ls -la node_modules/vite || true')

// Self-heal: force re-install vite (no-save) in case the package was truncated/corrupted
// This is intentionally redundant with `npm ci`, but has proven useful with flaky caches.
console.log('[vercel-prebuild] Attempting self-heal reinstall: vite@7.2.7')
log('npm i --no-save --prefer-online vite@7.2.7')

if (!exists(cliPath)) {
  console.log('[vercel-prebuild] STILL MISSING after reinstall:', cliPath)
  console.log('[vercel-prebuild] Failing build to force visibility of the issue.')
  process.exit(1)
}

console.log('[vercel-prebuild] Self-heal OK: found', cliPath)


