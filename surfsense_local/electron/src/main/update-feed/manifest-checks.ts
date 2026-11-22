// What a signed manifest must still hold before electron-updater acts on it. The
// signature says SurfSense wrote it; these say it is one electron-updater can use.
const RELEASE_VERSION = /^\d+\.\d+\.\d+$/

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

/** Why GitHub's manifest is unusable, or null: a release version and at least one file. */
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
