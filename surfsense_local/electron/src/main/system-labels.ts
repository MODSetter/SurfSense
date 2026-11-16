// This machine in the desktop telemetry contract's words (docs/contracts/05):
// the X-SurfSense-Platform / -OS headers and the usage report's platform and os.
// null when the machine is none of them, so nothing outside the enums leaves.

export type PlatformLabel =
  | "win32-x64"
  | "win32-arm64"
  | "darwin-arm64"
  | "darwin-x64"
  | "linux-x64"
  | "linux-arm64"

export type OsLabel = "windows-10" | "windows-11" | `macos-${number}` | "linux"

const PLATFORMS: ReadonlySet<string> = new Set<PlatformLabel>([
  "win32-x64",
  "win32-arm64",
  "darwin-arm64",
  "darwin-x64",
  "linux-x64",
  "linux-arm64",
])

// Windows 11 still reports itself as 10.0; its builds start at 22000.
const FIRST_WINDOWS_11_BUILD = 22000

export function platformLabel(platform: string, arch: string): PlatformLabel | null {
  const label = `${platform}-${arch}`
  return PLATFORMS.has(label) ? (label as PlatformLabel) : null
}

/** systemVersion is process.getSystemVersion(): "10.0.22631" on Windows, "15.1.0" on macOS. */
export function osLabel(platform: string, systemVersion: string): OsLabel | null {
  if (platform === "linux") return "linux"
  const parts = systemVersion.split(".").map((part) => Number.parseInt(part, 10))
  if (platform === "darwin") {
    const major = parts[0]
    return Number.isInteger(major) && major! >= 10 ? `macos-${major!}` : null
  }
  if (platform === "win32") {
    const [major, , build] = parts
    if (major !== 10 || !Number.isInteger(build)) return null
    return build! >= FIRST_WINDOWS_11_BUILD ? "windows-11" : "windows-10"
  }
  return null
}
