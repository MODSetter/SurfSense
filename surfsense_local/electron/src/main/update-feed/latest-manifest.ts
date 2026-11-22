import type { UpdateInfo } from "electron-updater"
import { parseUpdateInfo } from "electron-updater/out/providers/Provider.js"

import { feedBase } from "./feed-addresses.ts"
import { githubManifestProblem, mirrorManifestProblem } from "./manifest-checks.ts"
import { checkManifestSignature } from "./manifest-signature.ts"

export type ManifestRequest = { url: string; headers: Record<string, string> }

export type UpdateFeed = {
  /** GitHub's Latest release, or the admin policy's mirror. */
  base: string
  /** A mirror is for sites that reach nothing else: it serves the installers too. */
  mirror: boolean
  channelFile: string
  /** X-SurfSense-Version, -Platform and -OS for a mirror; GitHub gets no header of ours. */
  headers: Record<string, string>
  /** A manifest is used only when one of these signed it (UPDATE_PUBLIC_KEYS_HEX). */
  trustedKeys: readonly string[]
  /** The User-Agent the outbound session sets on every request; recorded here, not set. */
  userAgent?: string
  fetch: typeof fetch
  timeoutMs?: number
  /** The request to `base`, for Settings to show exactly what was sent. */
  onRequest?: (request: ManifestRequest) => void
  log?: (line: string) => void
}

// GitHub is the only host asked, so it gets the longer wait; a mirror keeps the
// contract's 10 s.
const GITHUB_TIMEOUT_MS = 30_000
const MIRROR_TIMEOUT_MS = 10_000

type Read = { info: UpdateInfo } | { problem: string }

async function readManifest(feed: UpdateFeed, url: string, timeoutMs: number): Promise<Read> {
  let file: Buffer
  try {
    const response = await feed.fetch(url, {
      headers: feed.headers,
      // GitHub answers latest/download with redirects to the release's own files.
      redirect: "follow",
      credentials: "omit",
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (response.status !== 200) return { problem: `HTTP ${response.status}` }
    // Bytes, not text: the signature covers what was served, which decoding could change.
    file = Buffer.from(await response.arrayBuffer())
  } catch (error) {
    const name = error instanceof Error ? error.name : ""
    return { problem: name === "TimeoutError" ? "timed out" : "unreachable" }
  }
  const checked = checkManifestSignature(file, feed.channelFile, feed.trustedKeys)
  if ("problem" in checked) return checked
  try {
    // Its errors quote the whole body, which is not for the log.
    return { info: parseUpdateInfo(checked.body.toString("utf8"), feed.channelFile, new URL(url)) }
  } catch {
    return { problem: "not YAML" }
  }
}

/**
 * The manifest for this platform, used only when SurfSense's key signed it. There
 * is no second source to fall back to, signed or not. A failure says which host
 * failed and why; Settings puts "Could not check for updates" in front of it.
 */
export async function latestManifest(feed: UpdateFeed): Promise<UpdateInfo> {
  const log = feed.log ?? (() => undefined)
  const base = feedBase(feed.base)
  const url = new URL(feed.channelFile, base).href
  const host = new URL(url).host
  const source = feed.mirror ? `the update mirror ${host}` : host
  feed.onRequest?.({
    url,
    headers: { ...(feed.userAgent ? { "User-Agent": feed.userAgent } : {}), ...feed.headers },
  })
  const read = await readManifest(
    feed,
    url,
    feed.timeoutMs ?? (feed.mirror ? MIRROR_TIMEOUT_MS : GITHUB_TIMEOUT_MS)
  )
  const problem =
    "problem" in read
      ? read.problem
      : feed.mirror
        ? mirrorManifestProblem(read.info, base)
        : githubManifestProblem(read.info)
  if (problem !== null) {
    log(`${source} could not be used (${problem})`)
    throw new Error(`${source} could not be used (${problem})`)
  }
  log(`signed manifest from ${source}`)
  return (read as { info: UpdateInfo }).info
}
