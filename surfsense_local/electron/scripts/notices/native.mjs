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

export function nativeNotices(root, components) {
  const entries = []
  const unstaged = []
  for (const { folder, files, ...entry } of components) {
    const dir = join(root, folder)
    if (!staged(dir)) {
      unstaged.push(entry.name)
      continue
    }
    const text = files
      .map((file) => join(dir, file))
      .filter((path) => existsSync(path))
      .map((path) => readFileSync(path, "utf8").trim())
      .join("\n\n")
    entries.push({ ...entry, tree: "native", text })
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
