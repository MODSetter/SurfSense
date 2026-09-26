// What Settings › About shows and copies into bug reports. Mirrored in
// frontend/src/lib/api.ts.
export type AppDetails = {
  version: string
  electron: string
  chrome: string
  node: string
  os: string
  arch: string
}

const OS_NAMES: Record<string, string> = {
  darwin: "macOS",
  win32: "Windows",
  linux: "Linux",
}

// Inputs are passed in, not read from `app`/`process`, so tests run without Electron.
export function appDetails(runtime: {
  version: string
  versions: { electron: string; chrome: string; node: string }
  platform: string
  systemVersion: string
  arch: string
}): AppDetails {
  const osName = OS_NAMES[runtime.platform] ?? runtime.platform
  return {
    version: runtime.version,
    electron: runtime.versions.electron,
    chrome: runtime.versions.chrome,
    node: runtime.versions.node,
    os: `${osName} ${runtime.systemVersion}`,
    arch: runtime.arch,
  }
}
