// Whether electron/audiocpp holds a server to keep, one to stage again, or none.
// A server staged before a family joined the pins answers that family's model
// with "unsupported model family hint", so it is not kept as it is.
import { existsSync } from "node:fs"
import { join } from "node:path"

import { unprovenFamilies } from "./built-families.mjs"
import { SERVER } from "./server-files.mjs"

/** `absent`, `current`, or `stale` with the reason, as a log line's end. */
export async function stagedServer(out, { exists = existsSync, probe = unprovenFamilies } = {}) {
  if (!exists(join(out, SERVER))) return { state: "absent" }
  const unproven = await probe(out)
  if (unproven.length === 0) return { state: "current" }
  const missing = unproven.filter(({ verdict }) => verdict === "missing").map(({ family }) => family)
  if (missing.length) return { state: "stale", reason: `was built without ${missing.join(", ")}` }
  const output = unproven[0].output.trim().slice(0, 400)
  return { state: "stale", reason: `did not run (${output || "it printed nothing"})` }
}
