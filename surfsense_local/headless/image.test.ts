import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { request } from "node:http"
import { after, before, describe, test } from "node:test"
import { setTimeout as sleep } from "node:timers/promises"

// The built image, as Docker Tests and Release Docker run it before any push.
// Off unless SURFSENSE_TEST_IMAGE names an image, as the packaging tests are off
// unless SURFSENSE_TEST_FROZEN_BACKEND names a binary.
const IMAGE = process.env.SURFSENSE_TEST_IMAGE
const PORT = Number(process.env.SURFSENSE_TEST_IMAGE_PORT ?? 4929)
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
async function start(): Promise<void> {
  docker("run", "-d", "--name", NAME, "-p", `127.0.0.1:${PORT}:80`, "-v", `${VOLUME}:/data`, IMAGE!)
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
  { method = "GET", host }: { method?: string; host?: string } = {}
): Promise<{ status: number; type: string; body: string }> {
  return new Promise((resolve, reject) => {
    const req = request(
      { host: "127.0.0.1", port: PORT, path, method, headers: host ? { host } : {} },
      (res) => {
        let body = ""
        res.setEncoding("utf8")
        res.on("data", (chunk) => (body += chunk))
        res.on("end", () =>
          resolve({ status: res.statusCode ?? 0, type: res.headers["content-type"] ?? "", body })
        )
      }
    )
    req.on("error", reject)
    req.end()
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
