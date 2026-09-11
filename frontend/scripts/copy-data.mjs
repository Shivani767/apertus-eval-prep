// Copies generated reports from the Python pipeline into frontend/public/data/
// so the dashboard reads canonical artifacts, never hardcoded numbers.
import { mkdirSync, copyFileSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '..', '..')
const reportsDir = join(repoRoot, 'reports')
const catalogDir = join(repoRoot, 'data', 'catalog')
const outDir = join(repoRoot, 'frontend', 'public', 'data')

mkdirSync(outDir, { recursive: true })

function copyDir(src, dest) {
  if (!existsSync(src)) {
    console.warn('missing:', src)
    return
  }
  mkdirSync(dest, { recursive: true })
  for (const f of readdirSync(src)) {
    if (f.endsWith('.json')) {
      copyFileSync(join(src, f), join(dest, f))
    }
  }
}

for (const sub of ['dashboard', 'ers', 'failures', 'pareto']) {
  copyDir(join(reportsDir, sub), join(outDir, sub))
}
copyDir(catalogDir, join(outDir, 'catalog'))
copyFileSync(join(repoRoot, 'results', 'registry_paper.jsonl'), join(outDir, 'registry.jsonl'))
console.log('data copied to', outDir)
