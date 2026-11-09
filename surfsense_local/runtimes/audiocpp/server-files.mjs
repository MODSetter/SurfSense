// The server and the ggml libraries beside it, its licence, and the curated
// families' model specs: what the sidecar runs, copied into the stage.
import { chmodSync, copyFileSync, mkdirSync, readdirSync, readlinkSync, symlinkSync } from "node:fs"
import { dirname, join } from "node:path"

import { FAMILIES } from "./pins.mjs"

export const SERVER = process.platform === "win32" ? "audiocpp_server.exe" : "audiocpp_server"
const LIBRARY = /\.(dylib|so)(\.\d+)*$|\.dll$/i

/** The shallowest server under `root`. */
function findServer(root) {
  let level = [root]
  while (level.length) {
    const next = []
    for (const dir of level) {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (entry.isFile() && entry.name === SERVER) return join(dir, entry.name)
        if (entry.isDirectory()) next.push(join(dir, entry.name))
      }
    }
    level = next
  }
}

/** `binaries` holds the server; `source` has LICENSE and model_specs at its top. */
export function copyServerFiles({ binaries, source }, stage) {
  const server = findServer(binaries)
  if (!server) throw new Error(`no ${SERVER} under ${binaries}`)
  // ggml loads its CPU libraries from beside the server. Links stay links:
  // the loader resolves the versioned names they carry.
  for (const entry of readdirSync(dirname(server), { withFileTypes: true })) {
    if (entry.name !== SERVER && !LIBRARY.test(entry.name)) continue
    const from = join(dirname(server), entry.name)
    const to = join(stage, entry.name)
    if (entry.isSymbolicLink()) {
      symlinkSync(readlinkSync(from), to)
      continue
    }
    copyFileSync(from, to)
    if (process.platform !== "win32") chmodSync(to, 0o755)
  }

  copyFileSync(join(source, "LICENSE"), join(stage, "LICENSE"))
  const specs = join(source, "model_specs")
  mkdirSync(join(stage, "model_specs"))
  for (const family of FAMILIES) {
    copyFileSync(join(specs, `${family}.json`), join(stage, "model_specs", `${family}.json`))
  }
}
