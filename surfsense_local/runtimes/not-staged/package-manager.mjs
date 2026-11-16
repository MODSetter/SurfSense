// The package manager that installs build tools here: the platform's, or on
// Linux the distribution family's, read from os-release. null where unknown.
import { readFileSync } from "node:fs"

const LINUX = [
  ["apt", ["debian", "ubuntu"]],
  ["dnf", ["fedora", "rhel"]],
  ["pacman", ["arch"]],
]

export function packageManager() {
  if (process.platform === "darwin") return "brew"
  if (process.platform === "win32") return "winget"
  let release
  try {
    release = readFileSync("/etc/os-release", "utf8")
  } catch {
    return null
  }
  const ids = [...release.matchAll(/^ID(?:_LIKE)?="?([^"\n]*)"?$/gm)].flatMap((m) => m[1].split(" "))
  return LINUX.find(([, family]) => family.some((id) => ids.includes(id)))?.[0] ?? null
}
