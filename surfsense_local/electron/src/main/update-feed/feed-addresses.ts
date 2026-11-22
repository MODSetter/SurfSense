// Where update manifests come from (contract 05, part A; ADR 0091): GitHub's
// Latest release, or an admin policy's mirror. Installers download from the
// release the manifest's version names.

const RELEASES = "https://github.com/MODSetter/SurfSense/releases"

/** It moves only when a release is published. */
export const GITHUB_LATEST_DOWNLOAD = `${RELEASES}/latest/download/`

export function githubReleaseDownload(version: string): string {
  return `${RELEASES}/download/v${version}/`
}

/** A feed base that file names resolve under, as electron-updater's newBaseUrl makes it. */
export function feedBase(base: string): string {
  return base.endsWith("/") ? base : `${base}/`
}

/**
 * The signed manifest for this platform, under electron-builder's names for its
 * `release` channel. Apps before 2.4.0 read the `stable` channel's, which every
 * release after 2.4.0 freezes on 2.4.0 for them.
 */
export function channelFile(platform: string, arch: string): string {
  if (platform === "darwin") return "release-mac.yml"
  if (platform === "linux") return arch === "x64" ? "release-linux.yml" : `release-linux-${arch}.yml`
  return "release.yml"
}
