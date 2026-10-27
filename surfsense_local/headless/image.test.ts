import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { request } from "node:http"
import { request as secureRequest } from "node:https"
import { after, before, describe, test } from "node:test"
import { setTimeout as sleep } from "node:timers/promises"

// The built image, as Docker Tests and Release Docker run it before any push.
// Off unless SURFSENSE_TEST_IMAGE names an image, as the packaging tests are off
// unless SURFSENSE_TEST_FROZEN_BACKEND names a binary.
const IMAGE = process.env.SURFSENSE_TEST_IMAGE
const PORT = Number(process.env.SURFSENSE_TEST_IMAGE_PORT ?? 4929)
const HTTPS_PORT = PORT + 14
const NAME = "surfsense-image-test"
const VOLUME = "surfsense-image-test-data"

function docker(...args: string[]): string {
  return execFileSync("docker", args, { encoding: "utf8", stdio: "pipe" }).trim()
}

function quietly(...args: string[]): void {
  try {
    docker(...args)
  } catch {}
}

// A first start migrates and loads the parser pack, so it gets the healthcheck's whole start period.
async function start(env: Record<string, string> = {}): Promise<void> {
  const settings = Object.entries(env).flatMap(([key, value]) => ["-e", `${key}=${value}`])
  docker(
    "run", "-d", "--name", NAME,
    "-p", `127.0.0.1:${PORT}:80`,
    "-p", `127.0.0.1:${HTTPS_PORT}:443`,
    "-v", `${VOLUME}:/data`,
    ...settings,
    IMAGE!,
  )
  let status = "starting"
  for (let i = 0; i < 150 && status === "starting"; i++) {
    await sleep(2_000)
    status = docker("inspect", "-f", "{{.State.Health.Status}}", NAME)
  }
  if (status !== "healthy") {
    throw new Error(`not healthy: ${status}\n${docker("logs", NAME)}`)
  }
}

// Returns the exit code; the container is removed, its volume kept.
function stop(): string {
  docker("stop", "-t", "30", NAME)
  const code = docker("inspect", "-f", "{{.State.ExitCode}}", NAME)
  docker("rm", NAME)
  return code
}

// A digest, never the secret itself, so a failure's output carries nothing to steal.
function secretDigest(): string {
  return docker("exec", NAME, "sha256sum", "/data/secret").split(" ")[0]
}

function get(
  path: string,
  {
    method = "GET",
    host,
    headers = {},
    json,
  }: { method?: string; host?: string; headers?: Record<string, string>; json?: unknown } = {}
): Promise<{ status: number; type: string; body: string; cookie: string; setCookie: string; location: string }> {
  const payload = json === undefined ? undefined : JSON.stringify(json)
  const sent = {
    ...(host ? { host } : {}),
    ...(payload ? { "content-type": "application/json", "content-length": String(Buffer.byteLength(payload)) } : {}),
    ...headers,
  }
  return new Promise((resolve, reject) => {
    const req = request({ host: "127.0.0.1", port: PORT, path, method, headers: sent }, (res) => {
      let body = ""
      res.setEncoding("utf8")
      res.on("data", (chunk) => (body += chunk))
      res.on("end", () => {
        const setCookie = String(res.headers["set-cookie"] ?? "")
        resolve({
          status: res.statusCode ?? 0,
          type: res.headers["content-type"] ?? "",
          body,
          cookie: setCookie.split(";")[0],
          setCookie,
          location: String(res.headers.location ?? ""),
        })
      })
    })
    req.on("error", reject)
    req.end(payload)
  })
}

describe("the image", { skip: IMAGE ? false : "SURFSENSE_TEST_IMAGE names no image" }, () => {
  before(async () => {
    quietly("rm", "-f", NAME)
    quietly("volume", "rm", VOLUME)
    await start()
  })

  after(() => {
    quietly("rm", "-f", NAME)
    quietly("volume", "rm", VOLUME)
  })

  test("answers the API through Caddy", async () => {
    assert.equal((await get("/api/health")).status, 200)
  })

  test("serves the app", async () => {
    const page = await get("/")
    assert.equal(page.status, 200)
    assert.match(page.body, /<title>SurfSense/)
  })

  // The page alone loads with its title even when its bundle would not.
  test("serves the app's script as JavaScript", async () => {
    const src = (await get("/")).body.match(/<script[^>]+src="([^"]+)"/)?.[1]
    assert.ok(src, "the page names no script")
    // Relative, `./assets/…`, so the same build loads from Electron's file:// too.
    const script = await get(new URL(src, "http://localhost/").pathname)
    assert.equal(script.status, 200)
    assert.match(script.type, /javascript/)
  })

  test("refuses a host other than localhost while it has no password", async () => {
    assert.equal((await get("/api/health", { host: "surfsense.example.com" })).status, 403)
  })

  test("refuses the workers' internal routes from outside", async () => {
    assert.equal((await get("/api/internal/events", { method: "POST" })).status, 403)
  })

  // Office support unpacks TDF's LibreOffice debs into /data; they link against
  // these, which a headless conversion loads (ADR 0075). Downloading it here is too heavy.
  test("has the system libraries and a font a headless LibreOffice needs", () => {
    const libraries = docker("exec", NAME, "ldconfig", "-p")
    for (const name of [
      "libXinerama.so.1",
      "libX11-xcb.so.1",
      "libXext.so.6",
      "libSM.so.6",
      "libfontconfig.so.1",
      "libnss3.so",
      "libssl3.so",
      "libdbus-1.so.3",
      "libcairo.so.2",
      "libgio-2.0.so.0",
      "libcups.so.2",
    ]) {
      assert.match(libraries, new RegExp(`\\b${name.replaceAll(".", "\\.")}\\b`), `${name} is missing`)
    }
    assert.match(docker("exec", NAME, "ls", "/usr/share/fonts/truetype"), /dejavu/)
  })

  // Last: it replaces the container the others ask, as an image update does.
  test("stops cleanly and keeps its secret in a new container on the same /data", async () => {
    const before = secretDigest()
    assert.equal(stop(), "0")

    await start()
    assert.equal((await get("/api/health")).status, 200)
    assert.equal(secretDigest(), before)
    assert.equal(stop(), "0")
  })
})

// A second container, with a password and one allowed host: the sign-in, end to end through Caddy.
describe("the image with a password", { skip: IMAGE ? false : "SURFSENSE_TEST_IMAGE names no image" }, () => {
  const PASSWORD = "correct horse battery" // pragma: allowlist secret

  before(async () => {
    quietly("rm", "-f", NAME)
    quietly("volume", "rm", VOLUME)
    await start({ SURFSENSE_PASSWORD: PASSWORD, SURFSENSE_ALLOWED_HOSTS: "surfsense.lan" })
  })

  after(() => {
    quietly("rm", "-f", NAME)
    quietly("volume", "rm", VOLUME)
  })

  test("keeps the app's files and health open, and the API closed", async () => {
    assert.equal((await get("/")).status, 200)
    assert.equal((await get("/api/health")).status, 200)
    assert.equal((await get("/api/workspaces")).status, 401)
  })

  test("refuses a wrong password, opens the API for the right one, and closes it on sign-out", async () => {
    const wrong = await get("/access/sign-in", { method: "POST", json: { password: "nope" } }) // pragma: allowlist secret
    assert.equal(wrong.status, 401)

    const right = await get("/access/sign-in", { method: "POST", json: { password: PASSWORD } })
    assert.equal(right.status, 204)
    assert.match(right.setCookie, /HttpOnly/)
    assert.equal((await get("/api/workspaces", { headers: { cookie: right.cookie } })).status, 200)

    const out = await get("/access/sign-out", { method: "POST", headers: { cookie: right.cookie } })
    assert.equal(out.status, 204)
    assert.match(out.setCookie, /Max-Age=0/)
  })

  test("answers the allowed host, and refuses any other", async () => {
    assert.equal((await get("/", { host: "surfsense.lan" })).status, 200)
    assert.equal((await get("/", { host: "attacker.example" })).status, 403)
  })

  test("takes the host from the request, not from a forwarded header the client sends", async () => {
    const forged = await get("/", { host: "attacker.example", headers: { "x-forwarded-host": "localhost" } })
    assert.equal(forged.status, 403)
  })
})

// A third: HTTPS on a LAN under the container's own certificate authority, as a
// device that trusts its root reaches it.
describe("the image over HTTPS on a LAN", { skip: IMAGE ? false : "SURFSENSE_TEST_IMAGE names no image" }, () => {
  const PASSWORD = "correct horse battery" // pragma: allowlist secret
  let ca = ""

  function secure(path: string, json?: unknown): Promise<{ status: number; setCookie: string }> {
    const payload = json === undefined ? undefined : JSON.stringify(json)
    return new Promise((resolve, reject) => {
      const req = secureRequest(
        {
          host: "127.0.0.1",
          port: HTTPS_PORT,
          path,
          method: payload ? "POST" : "GET",
          servername: "surfsense.lan",
          ca,
          headers: {
            host: `surfsense.lan:${HTTPS_PORT}`,
            ...(payload ? { "content-type": "application/json", "content-length": String(Buffer.byteLength(payload)) } : {}),
          },
        },
        (res) => {
          res.resume()
          res.on("end", () => resolve({ status: res.statusCode ?? 0, setCookie: String(res.headers["set-cookie"] ?? "") }))
        },
      )
      req.on("error", reject)
      req.end(payload)
    })
  }

  before(async () => {
    quietly("rm", "-f", NAME)
    quietly("volume", "rm", VOLUME)
    await start({
      SURFSENSE_PASSWORD: PASSWORD,
      SURFSENSE_ALLOWED_HOSTS: "surfsense.lan",
      SURFSENSE_TLS: "internal",
      SURFSENSE_HTTPS_PORT: String(HTTPS_PORT),
    })
    // The root a user copies out once, as .env.example says.
    for (let i = 0; i < 30 && !ca; i++) {
      try {
        ca = docker("exec", NAME, "cat", "/data/home/.local/share/caddy/pki/authorities/local/root.crt")
      } catch {
        await sleep(1_000)
      }
    }
  })

  after(() => {
    quietly("rm", "-f", NAME)
    quietly("volume", "rm", VOLUME)
  })

  test("serves the app over HTTPS under a certificate the device trusts", async () => {
    assert.equal((await secure("/")).status, 200)
  })

  test("signs in over HTTPS with a Secure session cookie", async () => {
    const right = await secure("/access/sign-in", { password: PASSWORD })
    assert.equal(right.status, 204)
    assert.match(right.setCookie, /Secure/)
  })

  test("sends plain HTTP on the LAN name to HTTPS, and keeps it for the host itself", async () => {
    const lan = await get("/", { host: "surfsense.lan" })
    assert.equal(lan.status, 308)
    assert.equal(lan.location, `https://surfsense.lan:${HTTPS_PORT}/`)
    assert.equal((await get("/api/health")).status, 200)
  })
})
