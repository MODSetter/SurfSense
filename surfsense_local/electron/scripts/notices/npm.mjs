// `node scripts/notices/npm.mjs`: one fragment per desktop pnpm tree, from
// the production dependencies pnpm reports and the licence files each carries.
// frontend/ and electron/ are separate lockfiles, so each is asked on its own.
import { execFileSync } from "node:child_process"
import { fileURLToPath } from "node:url"

import { writeFragment } from "./fragments.mjs"
import { licenceText } from "./licence-files.mjs"

const TREES = {
  frontend: fileURLToPath(new URL("../../../frontend", import.meta.url)),
  electron: fileURLToPath(new URL("../..", import.meta.url)),
}

/** Entries from `pnpm licenses list --json`, whose `versions` and `paths` pair up. */
export function npmNotices(report, tree) {
  const entries = []
  for (const packages of Object.values(report)) {
    for (const pkg of packages) {
      pkg.versions.forEach((version, i) => {
        entries.push({ name: pkg.name, version, tree, license: pkg.license, text: licenceText(pkg.paths[i]) })
      })
    }
  }
  return entries
}

function pnpmLicences(dir) {
  const out = execFileSync("pnpm", ["licenses", "list", "--json", "--prod"], {
    cwd: dir,
    encoding: "utf8",
    maxBuffer: 256 * 1024 * 1024,
    // pnpm is pnpm.cmd on Windows, which only a shell runs.
    shell: process.platform === "win32",
  })
  return JSON.parse(out || "{}")
}

function main() {
  for (const [tree, dir] of Object.entries(TREES)) {
    const entries = npmNotices(pnpmLicences(dir), tree)
    const path = writeFragment(`npm-${tree}`, { entries })
    console.log(`${entries.length} npm packages from ${tree} in ${path}`)
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main()
