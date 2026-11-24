import path, { type PlatformPath } from "node:path"

/** What an update replaces, so nothing of the user's may be kept inside it. */
export function appInstallFolder(
  platform: NodeJS.Platform,
  execPath: string,
  paths: PlatformPath = path,
): string {
  const folder = paths.dirname(execPath)
  // <name>.app/Contents/MacOS/<name>
  return platform === "darwin" ? paths.resolve(folder, "..", "..") : folder
}

/** An AppImage's execPath is inside a mount that disappears when it exits. */
export function relaunchOptions(env: NodeJS.ProcessEnv): { execPath?: string } {
  return env.APPIMAGE ? { execPath: env.APPIMAGE } : {}
}
