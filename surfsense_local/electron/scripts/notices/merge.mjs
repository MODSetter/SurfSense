// `node scripts/notices/merge.mjs`: merge every fragment into the notices the
// installer ships, and fail the build when a dependency carries no licence text
// that a reviewed allowlist entry does not explain.
import { existsSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { FRAGMENTS, FRAGMENTS_DIR, NOTICES_DIR } from "./fragments.mjs"

const ALLOWLIST = fileURLToPath(new URL("./allowed-without-text.json", import.meta.url))
// Model packs ship no licence file upstream, so only their id is known.
const NEEDS_TEXT = new Set(["frontend", "electron", "python", "native"])
const TREE_ORDER = ["native", "frontend", "electron", "python", "model"]
const RULE = "=".repeat(78)

function allowance(allowlist, entry) {
  return allowlist.find((a) => a.tree === entry.tree && a.name === entry.name && a.reason?.trim())
}

function byTreeThenName(a, b) {
  return (
    TREE_ORDER.indexOf(a.tree) - TREE_ORDER.indexOf(b.tree) ||
    a.name.toLowerCase().localeCompare(b.name.toLowerCase()) ||
    a.version.localeCompare(b.version)
  )
}

/** `fragments` maps a fragment name to its content; absent ones are problems. */
export function mergeNotices(fragments, allowlist) {
  const problems = FRAGMENTS.filter((name) => !fragments[name]).map((name) => `no ${name} fragment`)
  const entries = []
  for (const fragment of Object.values(fragments)) {
    for (const entry of fragment.entries) {
      const { name, version, tree, license, text } = entry
      let note = entry.note ?? ""
      if (NEEDS_TEXT.has(tree) && !text?.trim()) {
        const allowed = allowance(allowlist, entry)
        if (allowed) note = [note, allowed.reason].filter(Boolean).join(" ")
        else problems.push(`${tree} ${name} ${version} has no licence text`)
      }
      entries.push({ name, version: version ?? "", tree, license: license ?? "UNKNOWN", text: text ?? "", note })
    }
  }
  return { entries: entries.sort(byTreeThenName), problems }
}

function plainText(entries) {
  const blocks = entries.map((e) => {
    const body = [e.note, e.text].filter(Boolean).join("\n\n")
    return `${RULE}\n${e.name} ${e.version} (${e.tree}): ${e.license}\n${RULE}\n\n${body}\n`
  })
  return `Third-party notices for SurfSense\n\n${blocks.join("\n")}`
}

export function writeNotices(dir, entries) {
  writeFileSync(join(dir, "THIRD_PARTY_NOTICES.json"), `${JSON.stringify({ entries }, null, 2)}\n`)
  writeFileSync(join(dir, "THIRD_PARTY_NOTICES.txt"), plainText(entries))
}

function readFragments() {
  const fragments = {}
  for (const name of FRAGMENTS) {
    const path = join(FRAGMENTS_DIR, `${name}.json`)
    if (existsSync(path)) fragments[name] = JSON.parse(readFileSync(path, "utf8"))
  }
  return fragments
}

function main() {
  const fragments = readFragments()
  const allowlist = JSON.parse(readFileSync(ALLOWLIST, "utf8"))
  const { entries, problems } = mergeNotices(fragments, allowlist)
  const unstaged = fragments.native?.unstaged ?? []
  if (unstaged.length) console.log(`not staged, so not in the notices: ${unstaged.join(", ")}`)
  if (problems.length) {
    console.error(`third-party notices are incomplete:\n  ${problems.join("\n  ")}`)
    console.error(`add the text, or a reviewed entry with a reason to ${ALLOWLIST}`)
    process.exitCode = 1
    return
  }
  writeNotices(NOTICES_DIR, entries)
  console.log(`${entries.length} third-party notices in ${NOTICES_DIR}`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main()
