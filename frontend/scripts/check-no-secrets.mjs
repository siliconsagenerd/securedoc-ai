// Fails the deploy if a secret name or a hardcoded backend host leaks into the
// shipped frontend source. The SPA must only ever call same-origin /api/* or
// /health; the API key belongs to the server-side proxy, never the bundle.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')

const FORBIDDEN = [
  /\bVITE_API_KEY\b/,
  /\bSECUREDOC_API_KEY\b/,
  /\bGEMINI_API_KEY\b/,
  /\bTOKEN_VAULT_KEY\b/,
  /localhost:8000/,
  /localhost:8080/,
  /127\.0\.0\.1:8000/,
  /127\.0\.0\.1:8080/,
]

// Files that are shipped to the browser (or its HTML). Config such as
// vite.config.ts legitimately references the dev backend and is excluded.
const TARGETS = [join(root, 'src'), join(root, 'index.html')]

function* walk(path) {
  const stat = statSync(path)
  if (stat.isDirectory()) {
    for (const entry of readdirSync(path)) yield* walk(join(path, entry))
  } else {
    yield path
  }
}

const hits = []
for (const target of TARGETS) {
  for (const file of walk(target)) {
    const text = readFileSync(file, 'utf8')
    for (const pattern of FORBIDDEN) {
      if (pattern.test(text)) {
        hits.push(`${relative(root, file)}: matches ${pattern}`)
      }
    }
  }
}

if (hits.length) {
  console.error('Frontend bundle would leak a secret or hardcoded backend host:')
  for (const hit of hits) console.error(`  - ${hit}`)
  process.exit(1)
}

console.log('check-no-secrets: frontend source is clean')
