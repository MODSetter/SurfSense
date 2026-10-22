import assert from "node:assert/strict"
import test from "node:test"

import type { ManifestRequest, UpdateFeed } from "./latest-manifest.ts"
import { surfSenseFeedOptions } from "./surfsense-feed-provider.ts"

const OUR_FEED = "https://updates.surfsense.com/api/updates/stable.yml"
const GITHUB_FEED =
  "https://github.com/MODSetter/SurfSense/releases/latest/download/stable.yml"
const RELEASE = "https://github.com/MODSetter/SurfSense/releases/download/v2.2.4/"
const HEADERS = {
  "X-SurfSense-Version": "2.2.3",
  "X-SurfSense-Platform": "win32-x64",
  "X-SurfSense-OS": "windows-11",
}

// stable.yml as a release carries it, and as our route rewrites it.
const GITHUB_MANIFEST = `version: 2.2.4
files:
  - url: SurfSense-Setup.exe
    sha512: c2hhNTEy
    size: 1234
path: SurfSense-Setup.exe
sha512: c2hhNTEy
releaseDate: '2026-10-20T10:00:00.000Z'
`
const OUR_MANIFEST = GITHUB_MANIFEST.replaceAll(
  "SurfSense-Setup.exe",
  `${RELEASE}SurfSense-Setup.exe`
)

type Answer = { status?: number; body?: string } | "hang" | "refused"
type SentRequest = { url: string; headers: Record<string, string>; redirect?: string }

/** The network as the provider sees it: an answer per address, every request kept. */
function network(answers: Record<string, Answer>) {
  const requests: SentRequest[] = []
  const fetchFrom = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    requests.push({
      url,
      headers: { ...(init?.headers as Record<string, string>) },
      redirect: init?.redirect,
    })
    const answer = answers[url] ?? "refused"
    if (answer === "refused") throw new TypeError("fetch failed")
    if (answer === "hang") {
      return new Promise<Response>((_, reject) => {
        // AbortSignal.timeout's timer is unref'd; this one keeps the test's loop alive.
        const backstop = setTimeout(() => reject(new Error("never aborted")), 5_000)
        init?.signal?.addEventListener("abort", () => {
          clearTimeout(backstop)
          reject(init.signal!.reason)
        })
      })
    }
    return new Response(answer.body ?? "", { status: answer.status ?? 200 })
  }) as typeof fetch
  return { fetch: fetchFrom, requests }
}

/** The provider as electron-updater's providerFactory builds it, with the install ID AppUpdater hands it. */
function provider(feed: Partial<UpdateFeed> & Pick<UpdateFeed, "fetch">) {
  const seen: ManifestRequest[] = []
  const options = surfSenseFeedOptions({
    base: "https://updates.surfsense.com/api/updates/",
    mirror: false,
    channelFile: "stable.yml",
    headers: HEADERS,
    onRequest: (request) => seen.push(request),
    ...feed,
  })
  const built = new options.updateProvider(options, {}, {
    isUseMultipleRangeRequest: false,
    platform: "win32",
    executor: null as never,
  })
  built.setRequestHeaders({ "x-user-staging-id": "7c1f0a52-3b8e-4c1d-9f2e-0a6b5c4d3e2f" })
  return { provider: built, seen }
}

function assertNoIdentifier(requests: SentRequest[]): void {
  for (const request of requests) {
    const names = Object.keys(request.headers).map((name) => name.toLowerCase())
    assert.equal(names.includes("x-user-staging-id"), false, request.url)
  }
}

test("our feed's manifest is used, asked with exactly the three SurfSense headers", async () => {
  const net = network({ [OUR_FEED]: { body: OUR_MANIFEST } })
  const { provider: feed, seen } = provider({ fetch: net.fetch })

  const info = await feed.getLatestVersion()

  assert.equal(info.version, "2.2.4")
  assert.deepEqual(net.requests, [
    { url: OUR_FEED, headers: HEADERS, redirect: "error" },
  ])
  assert.deepEqual(seen, [{ url: OUR_FEED, headers: HEADERS }])
  assert.deepEqual(
    feed.resolveFiles(info).map((file) => file.url.href),
    [`${RELEASE}SurfSense-Setup.exe`]
  )
})

const BROKEN_FEEDS: Array<[string, Answer]> = [
  ["answers 500", { status: 500, body: "oops" }],
  ["answers 404", { status: 404 }],
  ["is unreachable", "refused"],
  ["answers garbage", { body: "<html>Bad gateway</html>" }],
  ["answers YAML that is not a manifest", { body: "- a\n- b\n" }],
  ["names no version", { body: OUR_MANIFEST.replace("version: 2.2.4\n", "") }],
  [
    "names a file on another host",
    { body: OUR_MANIFEST.replaceAll(RELEASE, "https://downloads.example.com/") },
  ],
  [
    "names another version's release",
    { body: OUR_MANIFEST.replaceAll("/v2.2.4/", "/v2.2.3/") },
  ],
  [
    "names a file that is not an installer",
    { body: OUR_MANIFEST.replaceAll("SurfSense-Setup.exe", "SurfSense-Setup.sh") },
  ],
  [
    "names a bare file, which only GitHub's own manifest may",
    { body: GITHUB_MANIFEST },
  ],
]

for (const [problem, answer] of BROKEN_FEEDS) {
  test(`when our feed ${problem}, GitHub's manifest is used, asked with no SurfSense headers`, async () => {
    const net = network({ [OUR_FEED]: answer, [GITHUB_FEED]: { body: GITHUB_MANIFEST } })
    const { provider: feed } = provider({ fetch: net.fetch })

    const info = await feed.getLatestVersion()

    assert.equal(info.version, "2.2.4")
    assert.deepEqual(
      net.requests.map((request) => request.url),
      [OUR_FEED, GITHUB_FEED]
    )
    assert.deepEqual(net.requests[1]!.headers, {})
    assert.equal(net.requests[1]!.redirect, "follow")
    assert.deepEqual(
      feed.resolveFiles(info).map((file) => file.url.href),
      [`${RELEASE}SurfSense-Setup.exe`]
    )
  })
}

test("a feed that does not answer within the timeout falls back to GitHub", async () => {
  const net = network({ [OUR_FEED]: "hang", [GITHUB_FEED]: { body: GITHUB_MANIFEST } })
  const { provider: feed } = provider({ fetch: net.fetch, timeoutMs: 20 })

  const info = await feed.getLatestVersion()

  assert.equal(info.version, "2.2.4")
  assert.deepEqual(
    net.requests.map((request) => request.url),
    [OUR_FEED, GITHUB_FEED]
  )
})

test("the check fails only when GitHub fails too", async () => {
  const net = network({ [OUR_FEED]: { status: 502 }, [GITHUB_FEED]: { status: 503 } })
  const { provider: feed } = provider({ fetch: net.fetch })

  await assert.rejects(feed.getLatestVersion(), /github\.com \(HTTP 503\)/)
})

test("an admin's mirror is used alone: no GitHub fallback when it fails", async () => {
  const mirror = "https://updates.corp.example/surfsense"
  const net = network({ [GITHUB_FEED]: { body: GITHUB_MANIFEST } })
  const { provider: feed } = provider({ fetch: net.fetch, base: mirror, mirror: true })

  await assert.rejects(feed.getLatestVersion(), /updates\.corp\.example/)
  assert.deepEqual(
    net.requests.map((request) => request.url),
    [`${mirror}/stable.yml`]
  )
})

test("an admin's mirror serves its own files", async () => {
  const mirror = "https://updates.corp.example/surfsense/"
  const net = network({ [`${mirror}stable.yml`]: { body: GITHUB_MANIFEST } })
  const { provider: feed } = provider({ fetch: net.fetch, base: mirror, mirror: true })

  const info = await feed.getLatestVersion()

  assert.deepEqual(
    feed.resolveFiles(info).map((file) => file.url.href),
    [`${mirror}SurfSense-Setup.exe`]
  )
})

test("the install ID AppUpdater hands the provider is never sent", async () => {
  const net = network({ [OUR_FEED]: { status: 500 }, [GITHUB_FEED]: { body: GITHUB_MANIFEST } })
  const { provider: feed } = provider({ fetch: net.fetch })

  await feed.getLatestVersion()

  assert.equal(net.requests.length, 2)
  assertNoIdentifier(net.requests)
})
