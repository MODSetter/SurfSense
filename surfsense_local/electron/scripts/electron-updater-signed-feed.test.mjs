import assert from "node:assert/strict"
import { createHash, generateKeyPairSync, randomBytes } from "node:crypto"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { createServer, request } from "node:http"
import { createRequire } from "node:module"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { acceptAnyTrustedPublisher } from "../src/main/installer-signature/any-trusted-publisher.ts"
import { GITHUB_LATEST_DOWNLOAD } from "../src/main/update-feed/feed-addresses.ts"
import { signManifest } from "../src/main/update-feed/manifest-signature.ts"
import { attachUpdater } from "../src/main/updater.ts"

// electron-updater 6.8.9's own NsisUpdater, wired by the app's attachUpdater and
// provider, against a local server answering at GitHub's addresses: an update is
// ready only when release.yml carries SurfSense's signature, the installer is the
// one it names, and Windows vouches for the installer's signature (ADR 0091).
const require = createRequire(import.meta.url)
const updaterRequire = createRequire(require.resolve("electron-updater"))
const { NsisUpdater } = require("electron-updater")
const { ElectronHttpExecutor } = updaterRequire("./electronHttpExecutor")

const RELEASE_PATH = "/MODSetter/SurfSense/releases/download/v2.5.0/"
const MANIFEST_PATH = "/MODSetter/SurfSense/releases/latest/download/release.yml"

function keyPair() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519")
  return { privateKey, hex: Buffer.from(publicKey.export({ format: "jwk" }).x, "base64url").toString("hex") }
}
const KEY = keyPair()

/** release.yml as electron-builder writes it for `installer`, signed unless told not to. */
function releaseYml(installer, { version = "2.5.0", key = KEY.privateKey, signed = true } = {}) {
  const sha512 = createHash("sha512").update(installer).digest("base64")
  const body = Buffer.from(
    `version: ${version}\nfiles:\n  - url: SurfSense-Setup.exe\n    sha512: ${sha512}\n    size: ${installer.length}\n` +
      `path: SurfSense-Setup.exe\nsha512: ${sha512}\nreleaseDate: '2026-12-01T10:00:00.000Z'\n`
  )
  return signed ? signManifest(body, "release.yml", key) : body
}

/** GitHub as the updater sees it: whatever path is asked, on one local port. */
async function github(t, routes) {
  const asked = []
  const server = createServer((req, res) => {
    asked.push(req.url)
    const body = routes[req.url]
    if (body === undefined) return res.writeHead(404).end()
    res.writeHead(200, { "content-length": body.length }).end(body)
  })
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve))
  t.after(() => new Promise((resolve) => server.close(resolve)))
  const port = server.address().port
  const local = (url) => `http://127.0.0.1:${port}${new URL(url).pathname}`
  return { port, asked, fetch: (input, init) => fetch(local(String(input)), init) }
}

/** Electron's net replaced by node:http, every host routed to the local server. */
class LocalExecutor extends ElectronHttpExecutor {
  constructor(port) {
    super()
    this.port = port
  }
  createRequest(options, callback) {
    return request({ ...options, protocol: "http:", hostname: "127.0.0.1", host: undefined, port: this.port }, callback)
  }
}

/** The packaged app on 2.4.0 as electron-updater sees it, with its app-update.yml. */
function installedApp(t) {
  const dir = mkdtempSync(join(tmpdir(), "signed-feed-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const config = join(dir, "app-update.yml")
  writeFileSync(
    config,
    "owner: MODSetter\nrepo: SurfSense\nprovider: github\nchannel: stable\npublisherName:\n  - SurfSense\nupdaterCacheDirName: surfsense-test-updater\n"
  )
  return {
    version: "2.4.0",
    name: "SurfSense",
    isPackaged: true,
    appUpdateConfigPath: config,
    userDataPath: dir,
    baseCachePath: dir,
    whenReady: () => Promise.resolve(),
    quit() {},
    relaunch() {},
    onQuit() {},
  }
}

const silent = { info() {}, warn() {}, error() {}, debug() {} }

/** Check now, as Settings starts it, and the state the check ends in. */
async function checkNow(t, { routes, verify, feed = {} }) {
  const server = await github(t, routes)
  const updater = new NsisUpdater(null, installedApp(t))
  updater.logger = silent
  updater.httpExecutor = new LocalExecutor(server.port)
  const verified = []
  updater.verifyUpdateCodeSignature = async (names, file) => {
    verified.push({ names, installer: readFileSync(file) })
    return verify(names, file)
  }
  const settled = new Promise((resolve) => {
    const updates = attachUpdater(
      updater,
      (state) => {
        if (state.status === "ready" || state.status === "error" || state.status === "up-to-date") resolve(state)
      },
      {
        base: GITHUB_LATEST_DOWNLOAD,
        mirror: false,
        channelFile: "release.yml",
        headers: {},
        trustedKeys: [KEY.hex],
        fetch: server.fetch,
        ...feed,
      }
    )
    void updates.check()
  })
  return { state: await settled, asked: server.asked, verified }
}

const INSTALLER = randomBytes(256 * 1024)
const passes = async () => null

test("a signed manifest's installer downloads, matches its sha512, passes Windows' check and waits to install", async (t) => {
  const { state, asked, verified } = await checkNow(t, {
    routes: { [MANIFEST_PATH]: releaseYml(INSTALLER), [`${RELEASE_PATH}SurfSense-Setup.exe`]: INSTALLER },
    verify: passes,
  })

  assert.deepEqual(state, { status: "ready", version: "2.5.0" })
  assert.equal(asked[0], MANIFEST_PATH)
  assert.ok(asked.includes(`${RELEASE_PATH}SurfSense-Setup.exe`))
  // app-update.yml's publisher still reaches the verifier, which is what makes NsisUpdater call it.
  assert.equal(verified.length, 1)
  assert.deepEqual(verified[0].names, ["SurfSense"])
  assert.ok(verified[0].installer.equals(INSTALLER))
})

for (const [what, manifest, problem] of [
  ["carries no signature", releaseYml(INSTALLER, { signed: false }), "release.yml carries no SurfSense signature"],
  ["is signed by a key the app does not trust", releaseYml(INSTALLER, { key: keyPair().privateKey }), "the signature on release.yml does not match"],
  [
    "changed after it was signed",
    Buffer.from(releaseYml(INSTALLER).toString().replace("size: 262144", "size: 262145")),
    "the signature on release.yml does not match",
  ],
]) {
  test(`a manifest that ${what} is refused before anything downloads`, async (t) => {
    const { state, asked, verified } = await checkNow(t, {
      routes: { [MANIFEST_PATH]: manifest, [`${RELEASE_PATH}SurfSense-Setup.exe`]: INSTALLER },
      verify: passes,
    })

    assert.deepEqual(state, { status: "error", message: `github.com could not be used (${problem})` })
    assert.deepEqual(asked, [MANIFEST_PATH])
    assert.equal(verified.length, 0)
  })
}

test("an installer other than the one the signed manifest names is refused before Windows is asked", async (t) => {
  const { state, verified } = await checkNow(t, {
    routes: { [MANIFEST_PATH]: releaseYml(INSTALLER), [`${RELEASE_PATH}SurfSense-Setup.exe`]: randomBytes(INSTALLER.length) },
    verify: passes,
  })

  assert.equal(state.status, "error")
  assert.match(state.message, /sha512 checksum mismatch/)
  assert.equal(verified.length, 0)
})

test("an installer Windows does not vouch for is refused, signed manifest or not", async (t) => {
  const { state } = await checkNow(t, {
    routes: { [MANIFEST_PATH]: releaseYml(INSTALLER), [`${RELEASE_PATH}SurfSense-Setup.exe`]: INSTALLER },
    verify: async () => "Windows does not trust its signature (NotSigned)",
  })

  assert.deepEqual(state, {
    status: "error",
    message: "New version 2.5.0 is not signed by the application owner: Windows does not trust its signature (NotSigned)",
  })
})

test("a signed manifest naming the version already installed offers nothing", async (t) => {
  const { state, asked } = await checkNow(t, {
    routes: { [MANIFEST_PATH]: releaseYml(INSTALLER, { version: "2.4.0" }) },
    verify: passes,
  })

  assert.deepEqual(state, { status: "up-to-date" })
  assert.deepEqual(asked, [MANIFEST_PATH])
})

test("an admin's mirror serves the signed manifest and the installer, and GitHub is never asked", async (t) => {
  const { state, asked } = await checkNow(t, {
    routes: { "/surfsense/release.yml": releaseYml(INSTALLER), "/surfsense/SurfSense-Setup.exe": INSTALLER },
    verify: passes,
    feed: { base: "https://updates.corp.example/surfsense/", mirror: true },
  })

  assert.deepEqual(state, { status: "ready", version: "2.5.0" })
  assert.ok(asked.every((path) => path.startsWith("/surfsense/")), asked.join(", "))
})

const onWindows = { skip: process.platform !== "win32" && "Get-AuthenticodeSignature is Windows-only" }

test("on Windows, the app's verifier takes an update signed by another trusted publisher, and refuses an unsigned one", onWindows, async (t) => {
  // Node's own node.exe stands in for an installer signed under a name 2.4.0 never saw.
  const otherPublisher = readFileSync(process.execPath)
  const verify = acceptAnyTrustedPublisher(silent)
  if ((await verify([], process.execPath)) !== null) return t.skip("this node.exe is not Authenticode-signed")

  const signedElsewhere = await checkNow(t, {
    routes: { [MANIFEST_PATH]: releaseYml(otherPublisher), [`${RELEASE_PATH}SurfSense-Setup.exe`]: otherPublisher },
    verify,
  })
  assert.deepEqual(signedElsewhere.state, { status: "ready", version: "2.5.0" })

  const unsigned = Buffer.from("not an installer")
  const refused = await checkNow(t, {
    routes: { [MANIFEST_PATH]: releaseYml(unsigned), [`${RELEASE_PATH}SurfSense-Setup.exe`]: unsigned },
    verify,
  })
  assert.equal(refused.state.status, "error")
  assert.match(refused.state.message, /^New version 2\.5\.0 is not signed by the application owner: Windows does not trust its signature/)
})
