// Copies the generated site.json into frontend/public/data/ so the dashboard
// reads the canonical export, never hardcoded numbers.
import { mkdirSync, copyFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '..', '..')
const outDir = join(repoRoot, 'frontend', 'public', 'data', 'site')

const src = join(repoRoot, 'reports', 'site', 'site.json')
if (!existsSync(src)) {
  console.error('missing:', src, '- run: python -m apertus_eval_prep site')
  process.exit(1)
}
mkdirSync(outDir, { recursive: true })
copyFileSync(src, join(outDir, 'site.json'))
console.log('site.json copied to', outDir)

