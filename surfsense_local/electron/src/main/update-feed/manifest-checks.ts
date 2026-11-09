import { githubReleaseDownload } from "./feed-addresses.ts"

// What the updates.surfsense.com route may name, as it validates it too. A
// manifest outside these is never used: the check falls back to GitHub.
const RELEASE_VERSION = /^\d+\.\d+\.\d+$/
const RELEASE_FILE = /^SurfSense[-A-Za-z0-9._]*\.(exe|zip|dmg|AppImage|deb|rpm)$/

type Manifest = Record<string, unknown>

function asManifest(value: unknown): Manifest | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Manifest)
    : null
}

export function releaseVersion(value: unknown): string | null {
  const version = asManifest(value)?.version
  return typeof version === "string" && RELEASE_VERSION.test(version) ? version : null
}

// Every address electron-updater may download from: files[].url, the legacy
// top-level path, and packages' paths (nsis-web).
function addresses(manifest: Manifest): unknown[] {
  const files = Array.isArray(manifest.files) ? manifest.files : []
  const packages = asManifest(manifest.packages)
  return [
    ...files.map((file) => asManifest(file)?.url),
    ...(manifest.path === undefined ? [] : [manifest.path]),
    ...Object.values(packages ?? {}).map((entry) => asManifest(entry)?.path),
  ]
}

function hasFiles(manifest: Manifest): boolean {
  return Array.isArray(manifest.files) && manifest.files.length > 0
}

/** Why our feed's manifest is unusable, or null when it names only this version's GitHub release files. */
export function feedManifestProblem(value: unknown): string | null {
  const manifest = asManifest(value)
  if (manifest === null) return "not a manifest"
  const version = releaseVersion(manifest)
  if (version === null) return "no release version"
  const files = hasFiles(manifest) ? (manifest.files as unknown[]) : []
  // The route passes sha512 through untouched, so a file without one was mangled.
  if (!files.length || files.some((file) => typeof asManifest(file)?.sha512 !== "string")) {
    return "no files"
  }
  const prefix = githubReleaseDownload(version)
  const outside = addresses(manifest).some(
    (address) =>
      typeof address !== "string" ||
      !address.startsWith(prefix) ||
      !RELEASE_FILE.test(address.slice(prefix.length))
  )
  return outside ? "a file outside the GitHub release" : null
}

/** GitHub's own manifest is the source of truth, so only its shape is checked. */
export function githubManifestProblem(value: unknown): string | null {
  const manifest = asManifest(value)
  if (manifest === null) return "not a manifest"
  if (releaseVersion(manifest) === null) return "no release version"
  return hasFiles(manifest) ? null : "no files"
}

/** An admin's mirror serves its own files, but only over https. */
export function mirrorManifestProblem(value: unknown, base: string): string | null {
  const problem = githubManifestProblem(value)
  if (problem !== null) return problem
  const insecure = addresses(value as Manifest).some((address) => {
    if (typeof address !== "string") return true
    try {
      return new URL(address, base).protocol !== "https:"
    } catch {
      return true
    }
  })
  return insecure ? "a file not on https" : null
}
