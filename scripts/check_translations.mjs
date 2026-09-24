// Check the desktop app's translation catalogs for the SurfSense rules that
// `formatjs verify` does not know: key shape, unused keys, file layout.
// `formatjs verify` (its own pre-commit hook) owns missing and extra keys and
// placeholder structure. No dependencies, so the pre-commit job needs only the
// Node that ships on the runner.
//
// Run: node scripts/check_translations.mjs
// Exit code is 1 when anything is wrong.

import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(fileURLToPath(import.meta.url), "..", "..")
const FRONTEND = join(ROOT, "surfsense_local", "frontend")
const TRANSLATIONS = join(FRONTEND, "translations")
const CODE_ROOTS = [
  join(FRONTEND, "src"),
  join(ROOT, "surfsense_local", "electron", "src", "main"),
]
const FEATURES = join(FRONTEND, "src", "features")
const LOCALES = ["en", "ja", "de"]
// Prefixes that are not a feature folder: the app shell and Electron main's menu.
const EXTRA_PREFIXES = ["app", "menu"]
const PURPOSES = [
  "title",
  "body",
  "label",
  "placeholder",
  "button",
  "tooltip",
  "empty",
  "error",
  "toast",
  "aria",
  "link",
  "status",
]

const problems = []
const fail = (where, message) => problems.push(`${where}: ${message}`)

function readCatalog(locale) {
  const path = join(TRANSLATIONS, `${locale}.json`)
  const where = relative(ROOT, path)
  let text
  try {
    text = readFileSync(path, "utf8")
  } catch {
    fail(where, "missing")
    return {}
  }
  let data
  try {
    data = JSON.parse(text)
  } catch (error) {
    fail(where, `not JSON: ${error.message}`)
    return {}
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    fail(where, "must be one flat object")
    return {}
  }
  for (const [key, value] of Object.entries(data)) {
    if (typeof value !== "string") fail(where, `${key} is not a string (no nesting)`)
    else if (value !== value.trim()) fail(where, `${key} has a leading or trailing space`)
  }
  const sorted = Object.fromEntries(
    Object.entries(data).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
  )
  if (text !== `${JSON.stringify(sorted, null, "\t")}\n`) {
    fail(where, "not sorted and tab-indented; rewrite it with keys in order")
  }
  return data
}

function sourceFiles(dir) {
  const files = []
  for (const name of readdirSync(dir)) {
    if (name === "compiled" || name === "node_modules") continue
    const path = join(dir, name)
    if (statSync(path).isDirectory()) files.push(...sourceFiles(path))
    else if (/\.(ts|tsx)$/.test(name) && !/\.(test\.tsx?|d\.ts)$/.test(name))
      files.push(path)
  }
  return files
}

const catalogs = Object.fromEntries(LOCALES.map((l) => [l, readCatalog(l)]))
const english = catalogs.en

const features = new Set([
  ...readdirSync(FEATURES).filter((name) =>
    statSync(join(FEATURES, name)).isDirectory()
  ),
  ...EXTRA_PREFIXES,
])

// Every call names its id literally: formatMessage({ id: "key" }).
const used = new Set()
for (const root of CODE_ROOTS) {
  for (const file of sourceFiles(root)) {
    for (const match of readFileSync(file, "utf8").matchAll(
      /\bid:\s*"([a-z0-9_]+)"/g
    )) {
      used.add(match[1])
    }
  }
}

for (const key of Object.keys(english)) {
  const where = "translations/en.json"
  const [prefix, ...rest] = key.split("_")
  if (!/^[a-z0-9]+(_[a-z0-9]+)+$/.test(key)) {
    fail(where, `${key} is not snake_case <feature>_<surface>_<purpose>`)
  } else if (!features.has(prefix)) {
    fail(where, `${key} does not start with a feature folder, app or menu`)
  } else if (!rest.includes("error") && !PURPOSES.includes(rest.at(-1))) {
    fail(where, `${key} must end in one of ${PURPOSES.join(", ")}`)
  }
  if (!used.has(key)) fail(where, `${key} is never called as { id: "${key}" }`)
}

for (const problem of problems) console.log(problem)
console.log(
  `\nchecked ${Object.keys(english).length} keys in ${LOCALES.length} languages, ${problems.length} problems`
)
process.exit(problems.length > 0 ? 1 : 0)
