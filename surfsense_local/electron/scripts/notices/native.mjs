// `node scripts/notices/native.mjs`: the native runtimes' fragment, read from
// what the stage scripts left in electron/. Nothing is fetched here.
import { existsSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { writeFragment } from "./fragments.mjs"
import { NATIVE_COMPONENTS } from "./native-components.mjs"

const ELECTRON = fileURLToPath(new URL("../..", import.meta.url))

// A dev checkout, or a host where a runtime could not be built, leaves the
// folder absent or empty; that is reported, since no binary ships either.
function staged(folder) {
  return existsSync(folder) && readdirSync(folder).length > 0
}

function readText(path) {
  return existsSync(path) ? readFileSync(path, "utf8").trim() : ""
}

// Every listed file must hold text: COPYING alone names ripgrep's licences
// without their terms, so a partial stage fails rather than ships.
export function nativeNotices(root, components) {
  const entries = []
  const unstaged = []
  const missing = []
  for (const { folder, files, ...entry } of components) {
    const dir = join(root, folder)
    if (!staged(dir)) {
      unstaged.push(entry.name)
      continue
    }
    const texts = files.map((file) => [join(folder, file), readText(join(dir, file))])
    for (const [file, text] of texts) if (!text) missing.push(`${entry.name}: ${file}`)
    entries.push({ ...entry, tree: "native", text: texts.map(([, text]) => text).join("\n\n") })
  }
  if (missing.length) {
    throw new Error(`staged native runtimes lack licence text:\n  ${missing.join("\n  ")}`)
  }
  return { entries, unstaged }
}

function main() {
  const fragment = nativeNotices(ELECTRON, NATIVE_COMPONENTS)
  const path = writeFragment("native", fragment)
  console.log(`${fragment.entries.length} native runtimes in ${path}`)
  if (fragment.unstaged.length) console.log(`not staged: ${fragment.unstaged.join(", ")}`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main()
