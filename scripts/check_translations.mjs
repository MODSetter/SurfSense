// Check the desktop app's translation catalogs for the SurfSense rules that
// FormatJS's own tools do not know. `formatjs extract` writes en.json from the
// code, `formatjs verify` owns missing and extra keys and placeholder
// structure, and eslint-plugin-formatjs owns the id shape and placeholder
// values. No dependencies, so the pre-commit job needs only the runner's Node.
//
// Run: node scripts/check_translations.mjs
// Exit code is 1 when anything is wrong.

import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(fileURLToPath(import.meta.url), "..", "..")
const FRONTEND = join(ROOT, "surfsense_local", "frontend")
const TRANSLATIONS = join(FRONTEND, "translations")
const FEATURES = join(FRONTEND, "src", "features")
const LOCALES_TS = join(FRONTEND, "src", "i18n", "locales.ts")
// The one prefix that is not a feature folder: the app shell.
const EXTRA_PREFIXES = ["app"]

const problems = []
const fail = (where, message) => problems.push(`${where}: ${message}`)

// The shipped languages, read from the one list the app builds from rather
// than mirrored here, where a stale copy would skip a language in silence.
function shippedLocales() {
  const source = readFileSync(LOCALES_TS, "utf8")
  const list = source.match(/export const LOCALES = \[([^\]]*)\]/)?.[1]
  if (!list) {
    fail(relative(ROOT, LOCALES_TS), "no LOCALES array to read")
    return []
  }
  return [...list.matchAll(/"([^"]+)"/g)].map((match) => match[1])
}

const LOCALES = shippedLocales()

// A catalog with no entry in LOCALES is never bundled; a locale with no
// catalog leaves the app showing English under that language's name.
const onDisk = readdirSync(TRANSLATIONS)
  .filter((name) => name.endsWith(".json"))
  .map((name) => name.replace(/\.json$/, ""))
for (const locale of onDisk) {
  if (!LOCALES.includes(locale)) {
    fail(`translations/${locale}.json`, "has no entry in i18n/locales.ts")
  }
}

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
  for (const [key, value] of Object.entries(data)) {
    if (typeof value !== "string") fail(where, `${key} is not a string (no nesting)`)
    else if (value !== value.trim()) fail(where, `${key} has a leading or trailing space`)
    // ICU's escape character; FormatJS's syntax guide asks for ’ in visible text.
    else if (value.includes("'")) fail(where, `${key} has a straight apostrophe; write ’`)
  }
  // The layout `formatjs extract` writes for en.json, kept by hand in the
  // others. Line endings are git's to decide: core.autocrlf checks these files
  // out with CRLF on Windows, which is not a formatting mistake.
  const sorted = Object.fromEntries(
    Object.entries(data).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
  )
  if (text.replace(/\r\n/g, "\n") !== `${JSON.stringify(sorted, null, 2)}\n`) {
    fail(where, "not sorted with two-space indent; rewrite it with keys in order")
  }
  return data
}

const catalogs = Object.fromEntries(LOCALES.map((l) => [l, readCatalog(l)]))

const features = new Set([
  ...readdirSync(FEATURES).filter((name) =>
    statSync(join(FEATURES, name)).isDirectory()
  ),
  ...EXTRA_PREFIXES,
])

// A deleted feature folder leaves its ids behind with a prefix nothing owns.
for (const key of Object.keys(catalogs.en)) {
  if (!features.has(key.split("_")[0])) {
    fail("translations/en.json", `${key} does not start with a feature folder or app`)
  }
}

for (const problem of problems) console.log(problem)
console.log(
  `\nchecked ${Object.keys(catalogs.en).length} keys in ${LOCALES.length} languages, ${problems.length} problems`
)
process.exit(problems.length > 0 ? 1 : 0)
