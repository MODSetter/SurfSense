// The licence text a package carries at its top level, in whichever of the
// usual names and spellings it uses, and apart from it any NOTICE file.
import { existsSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

const LICENCE_FILE = /^(licen[cs]e|copying|unlicense)([-_.][^/]*)?$/i
// A NOTICE carries attribution, not licence terms, so it never passes the gate alone.
const NOTICE_FILE = /^notice([-_.][^/]*)?$/i
// license-checker.js and friends are code, not text.
const CODE = /\.(c|m)?(js|ts)$/i

function joined(dir, names, pattern) {
  return names
    .filter((name) => pattern.test(name) && !CODE.test(name))
    .map((name) => readFileSync(join(dir, name), "utf8").trim())
    .join("\n\n")
}

export function licenceFiles(dir) {
  if (!existsSync(dir)) return { text: "", notice: "" }
  const names = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name)
    .sort()
  return { text: joined(dir, names, LICENCE_FILE), notice: joined(dir, names, NOTICE_FILE) }
}
