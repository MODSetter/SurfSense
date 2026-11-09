// Each file's Authenticode status as Windows reports it: "Valid", "NotSigned",
// "HashMismatch" and the rest.
import { execFileSync } from "node:child_process"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { powershell, quoted } from "./powershell.mjs"

/**
 * One status per file, in order, from one PowerShell run (about 5 s for 325
 * files). The paths go by file: a command line stops at 32,767 characters.
 */
export function signatureStatuses(files) {
  if (files.length === 0) return []
  const dir = mkdtempSync(join(tmpdir(), "surfsense-signatures-"))
  try {
    const list = join(dir, "files.txt")
    writeFileSync(list, files.join("\n"), "utf8")
    const read =
      `Get-Content -LiteralPath ${quoted(list)} -Encoding UTF8 | ` +
      "ForEach-Object { (Get-AuthenticodeSignature -LiteralPath $_).Status.ToString() }"
    const statuses = execFileSync(powershell(), ["-NoProfile", "-NonInteractive", "-Command", read], {
      encoding: "utf8",
      maxBuffer: 16 * 1024 * 1024,
    })
      .split(/\r?\n/)
      .filter(Boolean)
    if (statuses.length !== files.length) {
      throw new Error(`read ${statuses.length} signatures for ${files.length} files`)
    }
    return statuses
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}
