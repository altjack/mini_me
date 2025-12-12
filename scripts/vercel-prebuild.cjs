const fs = require('fs')
const crypto = require('crypto')

function safe(fn) {
  try {
    return fn()
  } catch (e) {
    console.log('[prevercel-build] ERROR:', String(e && e.message ? e.message : e))
    return null
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

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'))
}

console.log('node', process.version)

const vitePkgPath = 'node_modules/vite/package.json'
const reactPkgPath = 'node_modules/@vitejs/plugin-react/package.json'

const viteVer = safe(() => readJson(vitePkgPath).version)
const reactVer = safe(() => readJson(reactPkgPath).version)

if (viteVer) console.log('vite', viteVer)
if (reactVer) console.log('plugin-react', reactVer)

const vitePkg = safe(() => readJson(vitePkgPath))
if (vitePkg) {
  const keys = Object.keys(vitePkg.exports || {})
  console.log('vite.exports keys', JSON.stringify(keys))
}

const idx = 'node_modules/vite/dist/node/index.js'
console.log('vite.dist.node.index.js exists', exists(idx))

// Quick visibility into the common failure
const cli = 'node_modules/vite/dist/node/cli.js'
console.log('vite.dist.node.cli.js exists', exists(cli))
if (exists('node_modules/vite/dist/node')) {
  safe(() => {
    const entries = fs.readdirSync('node_modules/vite/dist/node').slice(0, 50)
    console.log('vite.dist.node entries (first 50)', JSON.stringify(entries))
  })
}

if (exists(idx)) {
  const buf = fs.readFileSync(idx)
  const hash = crypto.createHash('sha256').update(buf).digest('hex')
  console.log('vite.dist.node.index.js sha256', hash)

  const lines = buf.toString('utf8').split('\n')
  const hits = []
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('runtime')) hits.push(i)
  }
  console.log('vite.dist.node.index.js runtime_hits', hits.length)
  if (hits.length) {
    console.log('vite.dist.node.index.js sample_runtime_lines')
    hits.slice(0, 20).forEach((i) => {
      console.log(String(i + 1).padStart(5, ' ') + ':' + lines[i])
    })
  }
}

// Never fail the build from diagnostics
process.exit(0)


