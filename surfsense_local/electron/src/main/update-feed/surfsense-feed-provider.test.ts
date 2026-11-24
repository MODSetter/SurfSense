import assert from "node:assert/strict"
import { generateKeyPairSync, type KeyObject } from "node:crypto"
import test from "node:test"

import type { ManifestRequest, UpdateFeed } from "./latest-manifest.ts"
import { signManifest } from "./manifest-signature.ts"
import { surfSenseFeedOptions } from "./surfsense-feed-provider.ts"

const GITHUB_FEED = "https://github.com/MODSetter/SurfSense/releases/latest/download/release.yml"
const RELEASE = "https://github.com/MODSetter/SurfSense/releases/download/v2.5.0/"
const MIRROR = "https://updates.corp.example/surfsense/"
const MIRROR_HEADERS = {
  "X-SurfSense-Version": "2.4.0",
  "X-SurfSense-Platform": "win32-x64",
  "X-SurfSense-OS": "windows-11",
}

function keyPair(): { privateKey: KeyObject; hex: string } {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519")
  const x = publicKey.export({ format: "jwk" }).x as string
  return { privateKey, hex: Buffer.from(x, "base64url").toString("hex") }
}

const KEY = keyPair()

// release.yml as electron-builder writes it, before CI signs it.
const MANIFEST = `version: 2.5.0
files:
  - url: SurfSense-Setup.exe
    sha512: c2hhNTEy
    size: 1234
path: SurfSense-Setup.exe
sha512: c2hhNTEy
releaseDate: '2026-12-01T10:00:00.000Z'
`

function signed(body: string, channelFile = "release.yml", key = KEY.privateKey): string {
  return signManifest(Buffer.from(body), channelFile, key).toString()
}

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
    base: "https://github.com/MODSetter/SurfSense/releases/latest/download/",
    mirror: false,
    channelFile: "release.yml",
    headers: {},
    trustedKeys: [KEY.hex],
    userAgent: "SurfSense",
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

test("a manifest SurfSense signed is read straight from GitHub, with no header of ours", async () => {
  const net = network({ [GITHUB_FEED]: { body: signed(MANIFEST) } })
  const { provider: feed, seen } = provider({ fetch: net.fetch })

  const info = await feed.getLatestVersion()

  assert.equal(info.version, "2.5.0")
  assert.deepEqual(net.requests, [{ url: GITHUB_FEED, headers: {}, redirect: "follow" }])
  // The outbound session sets the User-Agent; Settings shows it.
  assert.deepEqual(seen, [{ url: GITHUB_FEED, headers: { "User-Agent": "SurfSense" } }])
  assert.deepEqual(
    feed.resolveFiles(info).map((file) => file.url.href),
    [`${RELEASE}SurfSense-Setup.exe`]
  )
})

const REFUSED: Array<[string, Answer, string]> = [
  ["comes back unsigned", { body: MANIFEST }, "release.yml carries no SurfSense signature"],
  [
    "is signed by a key the app does not trust",
    { body: signed(MANIFEST, "release.yml", keyPair().privateKey) },
    "the signature on release.yml does not match",
  ],
  [
    "changed after it was signed",
    { body: signed(MANIFEST).replace("version: 2.5.0", "version: 2.6.0") },
    "the signature on release.yml does not match",
  ],
  [
    "was signed for the Mac",
    { body: signed(MANIFEST, "release-mac.yml") },
    "the signature on release.yml does not match",
  ],
  ["is an HTML page", { body: "<html>Bad gateway</html>" }, "release.yml carries no SurfSense signature"],
  ["is signed but not YAML", { body: signed("version: [2.5.0\n") }, "not YAML"],
  ["is signed but not a manifest", { body: signed("- a\n- b\n") }, "not a manifest"],
  [
    "is signed but names no version",
    { body: signed(MANIFEST.replace("version: 2.5.0\n", "")) },
    "no release version",
  ],
  ["comes back as a 404", { status: 404 }, "HTTP 404"],
  ["comes back as a 503, even signed", { status: 503, body: signed(MANIFEST) }, "HTTP 503"],
  ["cannot be reached", "refused", "unreachable"],
]

for (const [what, answer, problem] of REFUSED) {
  test(`a release.yml that ${what} fails the check, and nothing else is asked`, async () => {
    const net = network({ [GITHUB_FEED]: answer })
    const { provider: feed } = provider({ fetch: net.fetch })

    // Settings writes "Could not check for updates: " in front of this.
    await assert.rejects(feed.getLatestVersion(), {
      message: `github.com could not be used (${problem})`,
    })
    assert.deepEqual(
      net.requests.map((request) => request.url),
      [GITHUB_FEED]
    )
  })
}

test("a GitHub that does not answer within the timeout fails the check", async () => {
  const net = network({ [GITHUB_FEED]: "hang" })
  const { provider: feed } = provider({ fetch: net.fetch, timeoutMs: 20 })

  await assert.rejects(feed.getLatestVersion(), {
    message: "github.com could not be used (timed out)",
  })
})

test("a release that carries an earlier Windows build's manifest points at that build's release", async () => {
  // A release with no signed Windows build keeps release.yml on the last one.
  const earlier = signed(MANIFEST.replaceAll("2.5.0", "2.4.0"))
  const net = network({ [GITHUB_FEED]: { body: earlier } })
  const { provider: feed } = provider({ fetch: net.fetch })

  const info = await feed.getLatestVersion()

  assert.deepEqual(
    feed.resolveFiles(info).map((file) => file.url.href),
    ["https://github.com/MODSetter/SurfSense/releases/download/v2.4.0/SurfSense-Setup.exe"]
  )
})

test("an admin's mirror is asked alone, with the three SurfSense headers, and serves its own files", async () => {
  const net = network({ [`${MIRROR}release.yml`]: { body: signed(MANIFEST) } })
  const { provider: feed, seen } = provider({
    fetch: net.fetch,
    base: MIRROR,
    mirror: true,
    headers: MIRROR_HEADERS,
  })

  const info = await feed.getLatestVersion()

  assert.deepEqual(net.requests, [
    { url: `${MIRROR}release.yml`, headers: MIRROR_HEADERS, redirect: "follow" },
  ])
  assert.deepEqual(seen, [
    { url: `${MIRROR}release.yml`, headers: { "User-Agent": "SurfSense", ...MIRROR_HEADERS } },
  ])
  assert.deepEqual(
    feed.resolveFiles(info).map((file) => file.url.href),
    [`${MIRROR}SurfSense-Setup.exe`]
  )
})

test("an admin's mirror must serve the file exactly as SurfSense signed it", async () => {
  const net = network({ [`${MIRROR}release.yml`]: { body: MANIFEST } })
  const { provider: feed } = provider({ fetch: net.fetch, base: MIRROR, mirror: true })

  await assert.rejects(feed.getLatestVersion(), {
    message:
      "the update mirror updates.corp.example could not be used (release.yml carries no SurfSense signature)",
  })
})

test("an admin's mirror that fails is not replaced by GitHub", async () => {
  const net = network({ [GITHUB_FEED]: { body: signed(MANIFEST) } })
  const { provider: feed } = provider({
    fetch: net.fetch,
    base: "https://updates.corp.example/surfsense",
    mirror: true,
  })

  await assert.rejects(feed.getLatestVersion(), {
    message: "the update mirror updates.corp.example could not be used (unreachable)",
  })
  assert.deepEqual(
    net.requests.map((request) => request.url),
    [`${MIRROR}release.yml`]
  )
})

test("a mirror's signed manifest naming a file over plain http is refused", async () => {
  const insecure = signed(MANIFEST.replaceAll("url: SurfSense", "url: http://files.corp.example/SurfSense"))
  const net = network({ [`${MIRROR}release.yml`]: { body: insecure } })
  const { provider: feed } = provider({ fetch: net.fetch, base: MIRROR, mirror: true })

  await assert.rejects(feed.getLatestVersion(), {
    message: "the update mirror updates.corp.example could not be used (a file not on https)",
  })
})

test("the install ID AppUpdater hands the provider is never sent", async () => {
  for (const mirror of [false, true]) {
    const net = network({
      [GITHUB_FEED]: { body: signed(MANIFEST) },
      [`${MIRROR}release.yml`]: { body: signed(MANIFEST) },
    })
    const { provider: feed } = provider({
      fetch: net.fetch,
      ...(mirror ? { base: MIRROR, mirror, headers: MIRROR_HEADERS } : {}),
    })

    await feed.getLatestVersion()

    assert.equal(net.requests.length, 1)
    const names = Object.keys(net.requests[0]!.headers).map((name) => name.toLowerCase())
    assert.equal(names.includes("x-user-staging-id"), false)
  }
})

test("differential updates ask GitHub's CDN for one range at a time", () => {
  // AppUpdater builds every provider with multi-range requests on
  // (createProviderRuntimeOptions); the release CDN answers those with 501.
  const options = surfSenseFeedOptions({
    base: "https://github.com/MODSetter/SurfSense/releases/latest/download/",
    mirror: false,
    channelFile: "release.yml",
    headers: {},
    trustedKeys: [KEY.hex],
    userAgent: "SurfSense",
    fetch: network({}).fetch,
  })
  const built = new options.updateProvider(options, {}, {
    isUseMultipleRangeRequest: true,
    platform: "win32",
    executor: null as never,
  })

  assert.equal(built.isUseMultipleRangeRequest, false)
})
