/**
 * Why Electron stopped starting opencode, for the API: it fails an Agentic
 * turn at once rather than wait for an opencode that will not come up. The API
 * counts the file only when it is newer than the configuration it just wrote.
 */
import { writeFileSync } from "node:fs"
import { join } from "node:path"

const FAILURE_FILE = "opencode-failed.json"

export function recordOpencodeFailure(agentDir: string, reason: string): void {
  writeFileSync(join(agentDir, FAILURE_FILE), JSON.stringify({ reason }))
}
