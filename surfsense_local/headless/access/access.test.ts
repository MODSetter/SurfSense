import assert from "node:assert/strict"
import { mkdtempSync, rmSync, statSync } from "node:fs"
import type { AddressInfo } from "node:net"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test, type TestContext } from "node:test"

import { handOverToApp, setPassword } from "./password-store.ts"
import { startAccess } from "./server.ts"

const GATEWAY = "172.18.0.1"
// Sample passwords; nothing here guards anything real.
const PASSWORD = "correct horse battery" // pragma: allowlist secret
const NEW_PASSWORD = "a new long passphrase" // pragma: allowlist secret

type Ask = {
  method?: string
  path: string
  uri?: string
  host?: string
  client?: string
  cookie?: string
  origin?: string
  body?: unknown
}

async function serve(
  t: TestContext,
  options: {
    password?: string
    fromSetup?: boolean
    allowedHosts?: string
    signInOff?: boolean
  } = {},
) {
  const dataDir = mkdtempSync(join(tmpdir(), "surfsense-access-"))
  if (options.password) await setPassword(dataDir, options.password, options.fromSetup ? "setup" : "app")
  const server = await startAccess({
    dataDir,
    secret: "a".repeat(64),
    allowedHosts: options.allowedHosts ?? "",
    signInOff: options.signInOff ?? false,
    gateway: () => GATEWAY,
  })
  t.after(() => {
    server.close()
    rmSync(dataDir, { recursive: true, force: true })
  })
  const port = (server.address() as AddressInfo).port

  // As Caddy sends it: the browser's host, cookie and address in X-Forwarded-*.
  // (fetch drops a Host header of its own; Caddy's X-Forwarded-Host is what counts.)
  async function ask(request: Ask) {
    const headers: Record<string, string> = {
      "X-Forwarded-Host": request.host ?? "localhost:4929",
      "X-Forwarded-For": request.client ?? GATEWAY,
      "X-Forwarded-Proto": "http",
    }
    if (request.uri) headers["X-Forwarded-Uri"] = request.uri
    if (request.cookie) headers.Cookie = request.cookie
    if (request.origin) headers.Origin = request.origin
    if (request.body !== undefined) headers["Content-Type"] = "application/json"
    const response = await fetch(`http://127.0.0.1:${port}${request.path}`, {
      method: request.method ?? "GET",
      headers,
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
    })
    const cookie = response.headers.get("set-cookie")?.split(";")[0] ?? ""
    return { status: response.status, cookie, response }
  }
  const verify = (uri: string, rest: Omit<Ask, "path" | "uri"> = {}) =>
    ask({ path: "/verify", uri, ...rest }).then((r) => r.status)
  return { ask, verify, dataDir }
}

const LAN = { host: "surfsense.lan", client: "192.168.1.30" }

test("without a password, only the app's files open, on any machine, so it can be set up", async (t) => {
  const { verify } = await serve(t)

  assert.equal(await verify("/"), 200)
  assert.equal(await verify("/", LAN), 200)
  assert.equal(await verify("/api/documents"), 401)
  assert.equal(await verify("/api/documents", LAN), 401)
})

test("the first password is set from any browser, and signs it in", async (t) => {
  const { ask, verify } = await serve(t)

  const created = await ask({ method: "POST", path: "/access/password", ...LAN, body: { password: PASSWORD } })

  assert.equal(created.status, 204)
  assert.equal(await verify("/api/documents", LAN), 401)
  assert.equal(await verify("/api/documents", { ...LAN, cookie: created.cookie }), 200)
})

test("a password set in the server's setup is not changed from the app", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD, fromSetup: true })
  const { cookie } = await ask({ method: "POST", path: "/access/sign-in", body: { password: PASSWORD } })

  const changed = await ask({
    method: "POST",
    path: "/access/password",
    cookie,
    body: { current: PASSWORD, password: NEW_PASSWORD },
  })

  assert.equal(changed.status, 409)
  const { response } = await ask({ path: "/access/state", cookie })
  assert.equal(((await response.json()) as { source: string }).source, "setup")
})

test("with sign-in turned off, an allowed address opens with no password, and any other name is still refused", async (t) => {
  const { verify } = await serve(t, { signInOff: true, allowedHosts: "surfsense.example.com" })

  assert.equal(await verify("/api/documents", { host: "surfsense.example.com", client: "198.51.100.7" }), 200)
  // A page rebinding its own name to this address never names one of ours.
  assert.equal(await verify("/api/documents", { host: "evil.example", client: "198.51.100.7" }), 403)
})

test("with a password, every route but the app's files and health needs a session", async (t) => {
  const { verify } = await serve(t, { password: PASSWORD })

  assert.equal(await verify("/"), 200)
  assert.equal(await verify("/assets/main-abc.js"), 200)
  assert.equal(await verify("/api/health"), 200)
  assert.equal(await verify("/api/documents"), 401)
  // Caddy matches /api/* decoded, case-blind and with slashes merged; so must this.
  for (const uri of ["/%61pi/documents", "/API/documents", "//api/documents", "/x/../api/documents", "/%E0%A4%A"]) {
    assert.equal(await verify(uri), 401, uri)
  }
  // A provider fetches the instance's own client document, with no session.
  assert.equal(await verify("/plugins/oauth/client.json"), 200)
  // Opened beyond the host: another machine reaches the sign-in, not the data.
  assert.equal(await verify("/", { host: "surfsense.lan", client: "192.168.1.30" }), 200)
  assert.equal(await verify("/api/documents", { host: "surfsense.lan", client: "192.168.1.30" }), 401)
})

// The browser may come back on another name than it signed in on, such as
// 127.0.0.1 after localhost, and so without the cookie. The sign-in's own
// state and PKCE guard these, not the session (RFC 9700).
test("a sign-in's callback passes without a session, on any name the host is", async (t) => {
  const { verify } = await serve(t, { password: PASSWORD })

  assert.equal(await verify("/callback?code=c&state=s", { host: "127.0.0.1:4929" }), 200)
  assert.equal(await verify("/plugins/oauth/callback?code=c&state=s", { host: "127.0.0.1:4929" }), 200)
  assert.equal(await verify("/plugins/oauth/callback?code=c&state=s", { host: "surfsense.lan", client: "192.168.1.30" }), 200)
  // Only the callbacks themselves: a path beneath or beside one is still the data's.
  assert.equal(await verify("/callbacks", { host: "127.0.0.1:4929" }), 200)
  assert.equal(await verify("/api/callback"), 401)
})

test("signing in with the password opens every route; a wrong one does not", async (t) => {
  const { ask, verify } = await serve(t, { password: PASSWORD })

  const wrong = await ask({ method: "POST", path: "/access/sign-in", body: { password: "nope" } }) // pragma: allowlist secret
  assert.equal(wrong.status, 401)
  assert.equal(wrong.cookie, "")

  const right = await ask({
    method: "POST",
    path: "/access/sign-in",
    body: { password: PASSWORD },
  })
  assert.equal(right.status, 204)
  const flags = right.response.headers.get("set-cookie") ?? ""
  assert.match(flags, /HttpOnly/)
  // Strict: no other site's page, link or redirect ever carries it; a sign-in's
  // callback needs none.
  assert.match(flags, /SameSite=Strict/)
  assert.equal(await verify("/api/documents", { cookie: right.cookie }), 200)
})

test("the session cookie is Secure when the browser came over HTTPS", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD })

  const signedIn = await fetchWithProto(ask, "https")
  assert.match(signedIn, /Secure/)
})

async function fetchWithProto(ask: Awaited<ReturnType<typeof serve>>["ask"], proto: string) {
  // ask() sends http; repeat its request with the scheme Caddy reports.
  const probe = await ask({ path: "/access/state" })
  const port = new URL(probe.response.url).port
  const response = await fetch(`http://127.0.0.1:${port}/access/sign-in`, {
    method: "POST",
    headers: {
      "X-Forwarded-Host": "localhost:4929",
      "X-Forwarded-For": GATEWAY,
      "X-Forwarded-Proto": proto,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ password: PASSWORD }),
  })
  return response.headers.get("set-cookie") ?? ""
}

test("five wrong passwords in a minute slow the sixth guess, even a right one", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD })
  const guess = (password: string) =>
    ask({ method: "POST", path: "/access/sign-in", client: "192.168.1.30", host: "surfsense.lan", body: { password } })

  for (let i = 0; i < 5; i++) assert.equal((await guess("nope")).status, 401)
  const slowed = await guess(PASSWORD)
  assert.equal(slowed.status, 429)
  assert.ok(Number(slowed.response.headers.get("retry-after")) > 0)
  // Another client is not held up by this one's guesses.
  const other = await ask({
    method: "POST",
    path: "/access/sign-in",
    client: "192.168.1.31",
    host: "surfsense.lan",
    body: { password: PASSWORD },
  })
  assert.equal(other.status, 204)
})

test("guesses sent at once are counted before any is checked", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD })

  const statuses = await Promise.all(
    Array.from({ length: 20 }, () =>
      ask({ method: "POST", path: "/access/sign-in", ...LAN, body: { password: "nope" } }).then((r) => r.status), // pragma: allowlist secret
    ),
  )

  assert.equal(statuses.filter((status) => status === 401).length, 5)
  assert.equal(statuses.filter((status) => status === 429).length, 15)
})

test("sign-in and sign-out refuse a request from another site", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD })

  const forged = await ask({
    method: "POST",
    path: "/access/sign-in",
    origin: "https://evil.example",
    body: { password: PASSWORD },
  })
  assert.equal(forged.status, 403)
  const sameSite = await ask({
    method: "POST",
    path: "/access/sign-in",
    origin: "http://localhost:4929",
    body: { password: PASSWORD },
  })
  assert.equal(sameSite.status, 204)
})

test("signing out clears the browser's session", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD })
  const signedIn = await ask({ method: "POST", path: "/access/sign-in", body: { password: PASSWORD } })

  const out = await ask({ method: "POST", path: "/access/sign-out", cookie: signedIn.cookie })
  assert.equal(out.status, 204)
  assert.match(out.response.headers.get("set-cookie") ?? "", /Max-Age=0/)
})

test("changing the password needs the current one, and ends every other session", async (t) => {
  const { ask, verify } = await serve(t, { password: PASSWORD })
  const phone = await ask({ method: "POST", path: "/access/sign-in", body: { password: PASSWORD } })
  const laptop = await ask({ method: "POST", path: "/access/sign-in", body: { password: PASSWORD } })

  const withoutCurrent = await ask({
    method: "POST",
    path: "/access/password",
    cookie: laptop.cookie,
    body: { password: NEW_PASSWORD },
  })
  assert.equal(withoutCurrent.status, 403)

  const changed = await ask({
    method: "POST",
    path: "/access/password",
    cookie: laptop.cookie,
    body: { current: PASSWORD, password: NEW_PASSWORD },
  })
  assert.equal(changed.status, 204)
  assert.equal(await verify("/api/documents", { cookie: phone.cookie }), 401)
  assert.equal(await verify("/api/documents", { cookie: changed.cookie }), 200)
})

test("a password shorter than eight characters is refused", async (t) => {
  const { ask } = await serve(t)

  const short = await ask({ method: "POST", path: "/access/password", body: { password: "short" } }) // pragma: allowlist secret
  assert.equal(short.status, 422)
})

test("with allowed hosts named, any other host is refused before sign-in", async (t) => {
  const { verify } = await serve(t, { password: PASSWORD, allowedHosts: "surfsense.lan, 192.168.1.20" })

  assert.equal(await verify("/", { host: "surfsense.lan", client: "192.168.1.30" }), 200)
  assert.equal(await verify("/", { host: "192.168.1.20:4929", client: "192.168.1.30" }), 200)
  // A name a rebinding page points at this address is not one of them.
  assert.equal(await verify("/", { host: "attacker.example", client: "192.168.1.30" }), 403)
  assert.equal(await verify("/callback?code=c&state=s", { host: "attacker.example", client: "192.168.1.30" }), 403)
})

test("the state tells the app whether to show the sign-in", async (t) => {
  const { ask } = await serve(t, { password: PASSWORD })

  const before = await ask({ path: "/access/state" })
  const expected = { password: true, host: true, source: "app", signInOff: false }
  assert.deepEqual(await before.response.json(), { ...expected, signedIn: false })
  const signedIn = await ask({ method: "POST", path: "/access/sign-in", body: { password: PASSWORD } })
  const after = await ask({ path: "/access/state", cookie: signedIn.cookie })
  assert.deepEqual(await after.response.json(), { ...expected, signedIn: true })
})

test("the password is stored hashed, readable by its owner only", async (t) => {
  const { dataDir } = await serve(t, { password: PASSWORD })

  const { readFileSync } = await import("node:fs")
  const stored = readFileSync(join(dataDir, "access.json"), "utf8")
  assert.doesNotMatch(stored, /correct horse battery/)
  assert.equal(statSync(join(dataDir, "access.json")).mode & 0o777, 0o600)
})

test("once the setup stops setting it, the password stays and becomes the app's", async (t) => {
  const { ask, dataDir } = await serve(t, { password: PASSWORD, fromSetup: true })

  handOverToApp(dataDir)

  const { response } = await ask({ path: "/access/state" })
  assert.deepEqual(
    (({ password, source }) => ({ password, source }))((await response.json()) as Record<string, unknown>),
    { password: true, source: "app" },
  )
})

test("the workers' internal routes are refused to every browser, signed in or not", async (t) => {
  const { ask, verify } = await serve(t, { password: PASSWORD })
  const { cookie } = await ask({ method: "POST", path: "/access/sign-in", body: { password: PASSWORD } })
  const open = await serve(t, { signInOff: true })

  // Never "sign in first": nothing outside the container reaches them.
  assert.equal(await verify("/api/internal/events"), 403)
  assert.equal(await verify("/api/internal/events", { cookie }), 403)
  assert.equal(await verify("/%61pi/internal/events", { cookie }), 403)
  assert.equal(await open.verify("/api/internal/events"), 403)
})
