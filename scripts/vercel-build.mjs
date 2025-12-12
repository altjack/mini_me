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

function run(cmd, { inherit = true } = {}) {
  if (inherit) {
    execSync(cmd, { stdio: 'inherit' })
    return { ok: true }
  }

  try {
    const stdout = execSync(cmd, { stdio: ['ignore', 'pipe', 'pipe'] }).toString()
    return { ok: true, stdout }
  } catch (e) {
    return {
      ok: false,
      status: e?.status,
      stdout: String(e?.stdout ?? ''),
      stderr: String(e?.stderr ?? ''),
      message: String(e),
    }
  }
}

// If Vercel (or its builder) drops node_modules/vite/dist, Vite's own bin breaks.
// Workaround: fall back to npx which fetches a fresh copy in its own cache.
const localCli = 'node_modules/vite/dist/node/cli.js'

console.log('[vercel-build] node:', process.version)
console.log('[vercel-build] localCli exists:', exists(localCli))

// Try local first (faster), but fall back to npx if anything fails.
if (exists(localCli)) {
  console.log('[vercel-build] Trying local vite from node_modules...')

  // Print version (captured) for better debugging if the build fails
  const versionRes = run('node node_modules/vite/bin/vite.js --version', { inherit: false })
  if (versionRes.ok && versionRes.stdout) {
    console.log('[vercel-build] local vite --version:', versionRes.stdout.trim())
  } else if (!versionRes.ok) {
    console.log('[vercel-build] local vite --version failed, will fallback to npx')
    console.log('[vercel-build] stderr:', versionRes.stderr)
  }

  const buildRes = run('node node_modules/vite/bin/vite.js build', { inherit: false })
  if (buildRes.ok) {
    if (buildRes.stdout) process.stdout.write(buildRes.stdout)
    process.exit(0)
  }

  console.log('[vercel-build] Local vite build FAILED, falling back to npx vite@7.2.7')
  console.log('[vercel-build] local stdout:\n' + (buildRes.stdout || '(empty)'))
  console.log('[vercel-build] local stderr:\n' + (buildRes.stderr || '(empty)'))
}

console.log('[vercel-build] Using npx vite@7.2.7 build...')
run('npx --yes vite@7.2.7 build', { inherit: true })


