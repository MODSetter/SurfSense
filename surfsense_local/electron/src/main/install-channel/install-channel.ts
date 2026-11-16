import { existsSync, readFileSync } from "node:fs"
import { posix, win32 } from "node:path"

import { isOwnSnap } from "./own-snap.ts"

/** A package manager that installs and updates SurfSense in place of its own updater. */
export type InstallChannel = "scoop" | "aur" | "snap" | "flatpak" | "nix" | "apt"

const CHANNELS: readonly string[] = ["scoop", "aur", "snap", "flatpak", "nix", "apt"]

/** Written by install.sh and the apt docs; a deb installed by hand has none. */
export const APT_SOURCE = "/etc/apt/sources.list.d/surfsense.list"

type Env = Record<string, string | undefined>

/**
 * Which package manager owns this install's updates, or null when the app
 * updates itself. Read once at startup; anything it cannot read counts as no
 * channel, so a broken probe never blocks the app's own updates.
 */
export function installChannel(options: {
  platform: string
  env: Env
  execPath: string
  resourcesPath: string
  readFile?: (path: string) => string
  exists?: (path: string) => boolean
}): InstallChannel | null {
  const {
    platform,
    env,
    execPath,
    resourcesPath,
    readFile = (path) => readFileSync(path, "utf8"),
    exists = existsSync,
  } = options
  const { join } = platform === "win32" ? win32 : posix
  const read = (path: string): string | null => {
    try {
      return readFile(path).trim()
    } catch {
      return null
    }
  }
  const present = (path: string): boolean => {
    try {
      return exists(path)
    } catch {
      return false
    }
  }

  // Scoop, a PKGBUILD or a Nix derivation repackages the release and says so.
  const marker = read(join(resourcesPath, "install-channel"))
  if (marker !== null && CHANNELS.includes(marker)) return marker as InstallChannel
  if (platform !== "linux") return null

  if (isOwnSnap(env, execPath)) return "snap"
  if (env.FLATPAK_ID || present("/.flatpak-info")) return "flatpak"
  if (execPath.startsWith("/nix/store/")) return "nix"
  // The apt repository serves the release's own .deb, so only the source file tells them apart.
  if (read(join(resourcesPath, "package-type")) === "deb" && present(APT_SOURCE)) return "apt"
  return null
}
