// Where update manifests come from (contract 05, part A). Only the small
// manifest goes through us; installers download from the GitHub release.

export const SURFSENSE_FEED = "https://updates.surfsense.com/api/updates/"

const RELEASES = "https://github.com/MODSetter/SurfSense/releases"

/** Read directly whenever our feed fails; it moves only when a release is published. */
export const GITHUB_LATEST_DOWNLOAD = `${RELEASES}/latest/download/`

export function githubReleaseDownload(version: string): string {
  return `${RELEASES}/download/v${version}/`
}

/** A feed base that file names resolve under, as electron-updater's newBaseUrl makes it. */
export function feedBase(base: string): string {
  return base.endsWith("/") ? base : `${base}/`
}

/** electron-updater's names for the "stable" channel (Provider.getChannelFilePrefix). */
export function channelFile(platform: string, arch: string): string {
  if (platform === "darwin") return "stable-mac.yml"
  if (platform === "linux") return arch === "x64" ? "stable-linux.yml" : `stable-linux-${arch}.yml`
  return "stable.yml"
}
