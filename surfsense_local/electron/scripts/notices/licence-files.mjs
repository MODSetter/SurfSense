// The licence text a package carries at its top level, in whichever of the
// usual names and spellings it uses.
import { existsSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

const LICENCE_FILE = /^(licen[cs]e|copying|notice|unlicense)([-_.][^/]*)?$/i
// license-checker.js and friends are code, not text.
const CODE = /\.(c|m)?(js|ts)$/i

export function licenceText(dir) {
  if (!existsSync(dir)) return ""
  const names = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && LICENCE_FILE.test(entry.name) && !CODE.test(entry.name))
    .map((entry) => entry.name)
    .sort()
  return names.map((name) => readFileSync(join(dir, name), "utf8").trim()).join("\n\n")
}
