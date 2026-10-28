// The PowerShell electron-builder signs with: pwsh when the machine has it, as
// GitHub's Windows runners do, else Windows PowerShell.
import { execFileSync } from "node:child_process"

let chosen = null

export function powershell() {
  if (chosen) return chosen
  try {
    execFileSync("pwsh.exe", ["-NoProfile", "-NonInteractive", "-Command", "exit 0"], { stdio: "ignore" })
    chosen = "pwsh.exe"
  } catch {
    chosen = "powershell.exe"
  }
  return chosen
}

/** A single-quoted PowerShell string. */
export function quoted(value) {
  return `'${String(value).replace(/'/g, "''")}'`
}
