import type { UpdateInfo } from "electron-updater"
import { parseUpdateInfo } from "electron-updater/out/providers/Provider.js"

import { feedBase, GITHUB_LATEST_DOWNLOAD } from "./feed-addresses.ts"
import {
  feedManifestProblem,
  githubManifestProblem,
  mirrorManifestProblem,
} from "./manifest-checks.ts"

export type ManifestRequest = { url: string; headers: Record<string, string> }

export type UpdateFeed = {
  /** updates.surfsense.com's route, or the admin policy's mirror. */
  base: string
  /** A mirror is for sites that reach nothing else, so it has no GitHub fallback. */
  mirror: boolean
  channelFile: string
  /** X-SurfSense-Version, -Platform and -OS: sent to `base` only, never to GitHub. */
  headers: Record<string, string>
  /** The User-Agent the outbound session sets on every request; recorded here, not set. */
  userAgent?: string
  fetch: typeof fetch
  timeoutMs?: number
  /** The request to `base`, for Settings to show exactly what was sent. */
  onRequest?: (request: ManifestRequest) => void
  log?: (line: string) => void
}

// The contract's bound on our feed. GitHub gets longer: it is the last resort.
const FEED_TIMEOUT_MS = 10_000
const GITHUB_TIMEOUT_MS = 30_000

type Read = { info: UpdateInfo } | { problem: string }

async function readManifest(
  fetchFrom: typeof fetch,
  url: string,
  init: { headers: Record<string, string>; redirect: "error" | "follow" },
  timeoutMs: number,
  channelFile: string
): Promise<Read> {
  let text: string
  try {
    const response = await fetchFrom(url, {
      ...init,
      credentials: "omit",
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (response.status !== 200) return { problem: `HTTP ${response.status}` }
    text = await response.text()
  } catch (error) {
    const name = error instanceof Error ? error.name : ""
    return { problem: name === "TimeoutError" ? "timed out" : "unreachable" }
  }
  try {
    // Its errors quote the whole body, which is not for the log.
    return { info: parseUpdateInfo(text, channelFile, new URL(url)) }
  } catch {
    return { problem: "not YAML" }
  }
}

/**
 * The manifest for this channel: from our feed, else straight from GitHub (never
 * blocked by us). A failure says only which hosts failed and why; Settings puts
 * "Could not check for updates" in front of it.
 */
export async function latestManifest(feed: UpdateFeed): Promise<UpdateInfo> {
  const log = feed.log ?? (() => undefined)
  const base = feedBase(feed.base)
  const url = new URL(feed.channelFile, base).href
  const host = new URL(url).host
  feed.onRequest?.({
    url,
    headers: { ...(feed.userAgent ? { "User-Agent": feed.userAgent } : {}), ...feed.headers },
  })
  const ours = await readManifest(
    feed.fetch,
    url,
    // A redirect would carry the headers to another host; ours never redirects.
    { headers: feed.headers, redirect: feed.mirror ? "follow" : "error" },
    feed.timeoutMs ?? FEED_TIMEOUT_MS,
    feed.channelFile
  )

  if (feed.mirror) {
    const problem = "problem" in ours ? ours.problem : mirrorManifestProblem(ours.info, base)
    if (problem !== null) {
      log(`update mirror ${host} could not be used (${problem})`)
      throw new Error(`the update mirror ${host} could not be used (${problem})`)
    }
    log(`manifest from the update mirror ${host}`)
    return (ours as { info: UpdateInfo }).info
  }

  const problem = "problem" in ours ? ours.problem : feedManifestProblem(ours.info)
  if (problem === null) {
    log(`manifest from ${host}`)
    return (ours as { info: UpdateInfo }).info
  }
  log(`${host} could not be used (${problem}); asking github.com`)
  const github = await readManifest(
    feed.fetch,
    `${GITHUB_LATEST_DOWNLOAD}${feed.channelFile}`,
    { headers: {}, redirect: "follow" },
    feed.timeoutMs === undefined ? GITHUB_TIMEOUT_MS : feed.timeoutMs,
    feed.channelFile
  )
  const githubProblem =
    "problem" in github ? github.problem : githubManifestProblem(github.info)
  if (githubProblem !== null) {
    log(`github.com could not be used either (${githubProblem})`)
    throw new Error(`${host} (${problem}) and github.com (${githubProblem}) could not be used`)
  }
  log("manifest from github.com")
  return (github as { info: UpdateInfo }).info
}
