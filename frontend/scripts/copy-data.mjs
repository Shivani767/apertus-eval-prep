// Copies the generated site.json into frontend/public/data/ (deployed build)
// and frontend/src/data/ (typed test fixture). Both come from the same
// canonical export — the frontend never hardcodes research numbers.
import { mkdirSync, copyFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '..', '..')

const src = join(repoRoot, 'reports', 'site', 'site.json')
if (!existsSync(src)) {
  console.error('missing:', src, '- run: python -m apertus_eval_prep site')
  process.exit(1)
}
const publicDir = join(repoRoot, 'frontend', 'public', 'data', 'site')
mkdirSync(publicDir, { recursive: true })
copyFileSync(src, join(publicDir, 'site.json'))
const fixtureDir = join(repoRoot, 'frontend', 'src', 'data')
mkdirSync(fixtureDir, { recursive: true })
copyFileSync(src, join(fixtureDir, 'site.json'))
console.log('site.json copied to', publicDir, 'and', fixtureDir)

