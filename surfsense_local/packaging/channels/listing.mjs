// What every package manager lists SurfSense as. The version and checksums come
// from the release (release.mjs); these stay the same from one release to the next.

export const REPO = "MODSetter/SurfSense"
export const NAME = "SurfSense"
export const PUBLISHER = "SurfSense"
export const HOMEPAGE = "https://www.surfsense.com"
export const LICENSE = "Apache-2.0"

// One line for every channel, so it obeys the strictest rules, Homebrew's: no
// article, no product name, no platform, no comparison, not addressed to the reader.
export const SUMMARY = "Document research assistant that runs AI models locally"

// The snap's description (electron-builder.yml), for listings that take a paragraph.
export const DESCRIPTION =
  "SurfSense is a local-first desktop app for research over your own documents. " +
  "It parses and embeds them on this computer, answers questions about them with citations, " +
  "and runs its language, voice and image models locally."

/** Where GitHub serves `name` from the release tagged v`version`. */
export function downloadUrl(version, name) {
  return `https://github.com/${REPO}/releases/download/v${version}/${name}`
}

/** The release's page, which carries its notes. */
export function releaseNotesUrl(version) {
  return `https://github.com/${REPO}/releases/tag/v${version}`
}
