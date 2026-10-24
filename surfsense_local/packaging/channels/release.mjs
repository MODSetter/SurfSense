// The published release a channel's files describe, and GitHub's sha256 of each of
// its assets, so no installer is ever downloaded to hash it.
import { readFileSync } from "node:fs"

import { downloadUrl, releaseNotesUrl, REPO } from "./listing.mjs"

const DIGEST = /^sha256:([0-9a-f]{64})$/

/** GitHub's API address for the release tagged v`version`. */
export function releaseApiUrl(version) {
  return `https://api.github.com/repos/${REPO}/releases/tags/v${version}`
}

/**
 * The release's JSON as `gh api repos/<repo>/releases/tags/v<version>` prints it:
 * from `file` when given, else from GitHub's API, with GH_TOKEN when it is set.
 */
export async function readReleaseJson({ version, file, env = process.env, fetch = globalThis.fetch }) {
  if (file) return JSON.parse(readFileSync(file, "utf8"))
  const url = releaseApiUrl(version)
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "surfsense-packaging-channels",
    "X-GitHub-Api-Version": "2022-11-28",
  }
  if (env.GH_TOKEN) headers.Authorization = `Bearer ${env.GH_TOKEN}`
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(60_000) })
  if (!response.ok) {
    throw new Error(`${url} answered ${response.status} ${response.statusText}; is v${version} published?`)
  }
  return response.json()
}

/**
 * Release v`version` from its JSON. Refuses a release with another tag, a draft or
 * a prerelease; `asset(name)` refuses an asset that is missing, still uploading,
 * served from elsewhere, or that GitHub has no sha256 for.
 */
export function publishedRelease(json, version) {
  const tag = `v${version}`
  if (json.tag_name !== tag) throw new Error(`the release is tagged ${json.tag_name}, not ${tag}`)
  if (json.draft) throw new Error(`${tag} is a draft; publish it first`)
  if (json.prerelease) throw new Error(`${tag} is a prerelease; channels get stable releases only`)

  return {
    version,
    date: String(json.published_at ?? "").slice(0, 10),
    notesUrl: releaseNotesUrl(version),
    asset(name) {
      const found = (json.assets ?? []).filter((asset) => asset.name === name)
      if (found.length !== 1) throw new Error(`${tag} has no ${name}`)
      const [asset] = found
      if (asset.state && asset.state !== "uploaded") throw new Error(`${name} on ${tag} is still uploading`)
      const url = downloadUrl(version, name)
      if (asset.browser_download_url !== url) {
        throw new Error(`${name} on ${tag} is served from ${asset.browser_download_url}, not ${url}`)
      }
      const sha256 = DIGEST.exec(asset.digest ?? "")?.[1]
      if (!sha256) throw new Error(`${name} on ${tag} has no sha256 digest (${asset.digest}); re-run once its upload has finished`)
      return { url, sha256 }
    },
  }
}
