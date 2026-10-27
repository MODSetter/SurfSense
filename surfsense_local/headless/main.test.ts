import assert from "node:assert/strict"
import { spawn, type ChildProcess } from "node:child_process"
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test, type TestContext } from "node:test"
import { fileURLToPath } from "node:url"

const MAIN = fileURLToPath(new URL("main.ts", import.meta.url))

// Stands in for the backend's venv Python and for llama-server: `main.py` serves
// /health, the rest idle, and each records its pid and the environment it was given.
const FAKE_SIDECAR = `#!/usr/bin/env node
const fs = require("node:fs")
const http = require("node:http")
const path = require("node:path")
const [entry, queue] = process.argv.slice(2)
const name = path.basename(process.argv[1])
const role = name === "llama-server" || name === "caddy" ? name : entry === "main.py" ? "api" : "worker-" + queue
const keys = ["HF_HUB_OFFLINE", "SURFSENSE_LOCAL_SIGNED_REGISTRY", "SURFSENSE_LOCAL_RUNTIME", "HOME", "SURFSENSE_LOCAL_SECRET", "SURFSENSE_LOCAL_DATA_DIR", "SURFSENSE_PASSWORD", "SURFSENSE_LOCAL_DOMAIN"]
fs.writeFileSync(path.join(process.env.FAKE_LOG, role + ".json"),
  JSON.stringify({
    pid: process.pid,
    env: Object.fromEntries(keys.map((k) => [k, process.env[k]])),
    args: process.argv.slice(2),
    cwd: process.cwd(),
    caddy: Object.fromEntries(["SURFSENSE_API_PORT", "SURFSENSE_CHATGPT_CALLBACK_PORT", "SURFSENSE_FRONTEND_DIR", "SURFSENSE_ACCESS_PORT", "SURFSENSE_TLS_SITES", "SURFSENSE_HTTPS_PORT"].map((k) => [k, process.env[k]])),
    chatgptCallbackPort: process.env.SURFSENSE_LOCAL_CHATGPT_CALLBACK_PORT,
  }))
const caddyExit = Number(process.env.FAKE_CADDY_EXIT_AFTER_MS)
if (role === "caddy" && caddyExit) setTimeout(() => process.exit(4), caddyExit)
if (role === "api") {
  http.createServer((req, res) => res.writeHead(req.url === "/health" ? 200 : 404).end())
    .listen(Number(process.env.SURFSENSE_LOCAL_PORT), process.env.SURFSENSE_LOCAL_HOST)
  const after = Number(process.env.FAKE_API_EXIT_AFTER_MS)
  if (after) setTimeout(() => process.exit(3), after)
} else {
  setInterval(() => {}, 1000)
}
const slowStop = Number(process.env.FAKE_SLOW_STOP_MS)
if (slowStop && role.startsWith("worker-")) process.on("SIGTERM", () => setTimeout(() => process.exit(0), slowStop))
`

interface Run {
  child: ChildProcess
  dataDir: string
  log: string
  exited: Promise<number | null>
  ready: Promise<string>
}

function fake(path: string): void {
  mkdirSync(join(path, ".."), { recursive: true })
  writeFileSync(path, FAKE_SIDECAR)
  chmodSync(path, 0o755)
}

function startHeadless(
  t: TestContext,
  {
    env = {},
    llamaServer = false,
    caddy = false,
  }: { env?: Record<string, string>; llamaServer?: boolean; caddy?: boolean } = {},
): Run {
  const root = mkdtempSync(join(tmpdir(), "surfsense-headless-"))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const backend = join(root, "backend")
  fake(join(backend, ".venv", "bin", "python"))
  const dataDir = join(root, "data")
  const log = join(root, "log")
  mkdirSync(log)
  mkdirSync(join(root, "runtimes"))
  if (llamaServer) fake(join(root, "runtimes", "llamacpp", "llama-server"))
  const caddyEnv: Record<string, string> = {}
  if (caddy) {
    fake(join(root, "bin", "caddy"))
    mkdirSync(join(root, "caddy"))
    writeFileSync(join(root, "caddy", "Caddyfile"), "")
    Object.assign(caddyEnv, {
      SURFSENSE_LOCAL_CADDY: join(root, "bin", "caddy"),
      SURFSENSE_LOCAL_CADDYFILE: join(root, "caddy", "Caddyfile"),
      SURFSENSE_LOCAL_FRONTEND_DIR: join(root, "dist"),
    })
  }

  const child = spawn(process.execPath, [MAIN], {
    env: {
      ...process.env,
      SURFSENSE_LOCAL_BACKEND_DIR: backend,
      SURFSENSE_LOCAL_DATA_DIR: dataDir,
      SURFSENSE_LOCAL_MODELS_DIR: join(root, "models"),
      SURFSENSE_LOCAL_RUNTIMES_DIR: join(root, "runtimes"),
      SURFSENSE_LOCAL_SECRET: "",
      FAKE_LOG: log,
      ...caddyEnv,
      ...env,
    },
    stdio: ["ignore", "pipe", "pipe"],
  })
  t.after(() => {
    if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL")
  })
  const exited = new Promise<number | null>((resolve) => child.on("exit", (code) => resolve(code)))
  const ready = new Promise<string>((resolve, reject) => {
    let out = ""
    child.stdout?.on("data", (chunk) => {
      out += chunk
      const match = /ready (http:\/\/\S+)/.exec(out)
      if (match) resolve(match[1])
    })
    void exited.then((code) => reject(new Error(`exited ${code} before ready`)))
  })
  return { child, dataDir, log, exited, ready }
}

type Recorded = Record<
  string,
  {
    pid: number
    env: Record<string, string | undefined>
    args: string[]
    cwd: string
    caddy: Record<string, string | undefined>
    chatgptCallbackPort?: string
  }
>

/** Every fake's record, once `count` have written one: ready waits on the API alone. */
async function recorded(log: string, count = 4): Promise<Recorded> {
  const deadline = Date.now() + 15_000
  while (readdirSync(log).length < count && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  return Object.fromEntries(
    readdirSync(log).map((file) => [file.replace(/\.json$/, ""), JSON.parse(readFileSync(join(log, file), "utf8"))]),
  )
}

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

const skip = process.platform === "win32" ? "POSIX signals and a shebang fake" : false

test("ready once the API is healthy, with the API and three workers on the container's environment", { skip }, async (t) => {
  const run = startHeadless(t)
  const url = await run.ready
  assert.equal(readFileSync(join(run.dataDir, "api-url"), "utf8"), url)

  const children = await recorded(run.log)
  assert.deepEqual(Object.keys(children).sort(), ["api", "worker-ingest", "worker-plugins", "worker-studio"])
  const secret = readFileSync(join(run.dataDir, "secret"), "utf8").trim()
  for (const { env } of Object.values(children)) {
    assert.deepEqual(env, {
      HF_HUB_OFFLINE: "1",
      SURFSENSE_LOCAL_SIGNED_REGISTRY: "1",
      SURFSENSE_LOCAL_RUNTIME: "docker",
      HOME: join(run.dataDir, "home"),
      SURFSENSE_LOCAL_SECRET: secret,
      SURFSENSE_LOCAL_DATA_DIR: run.dataDir,
    })
  }
  assert.ok(existsSync(join(run.dataDir, "home")))
  run.child.kill("SIGTERM")
})

for (const signal of ["SIGTERM", "SIGINT"] as const) {
  test(`${signal} stops every child and exits 0`, { skip }, async (t) => {
    const run = startHeadless(t)
    await run.ready
    const pids = Object.values(await recorded(run.log)).map((c) => c.pid)
    run.child.kill(signal)
    assert.equal(await run.exited, 0)
    assert.deepEqual(pids.filter(alive), [])
    assert.equal(existsSync(join(run.dataDir, "api-url")), false)
  })
}

test("the API exiting stops the rest and exits non-zero, so the container restarts", { skip }, async (t) => {
  const run = startHeadless(t, { env: { FAKE_API_EXIT_AFTER_MS: "700" } })
  await run.ready
  const pids = Object.values(await recorded(run.log)).map((c) => c.pid)
  assert.notEqual(await run.exited, 0)
  assert.deepEqual(pids.filter(alive), [])
})

test("a secret given in the environment reaches the API and the workers, and no model server", { skip }, async (t) => {
  const run = startHeadless(t, { env: { SURFSENSE_LOCAL_SECRET: "the-operators-secret" }, llamaServer: true }) // pragma: allowlist secret
  await run.ready
  const children = await recorded(run.log, 5)
  for (const name of ["api", "worker-ingest", "worker-studio", "worker-plugins"]) {
    assert.equal(children[name]?.env.SURFSENSE_LOCAL_SECRET, "the-operators-secret", name) // pragma: allowlist secret
  }
  assert.equal(children["llama-server"]?.env.SURFSENSE_LOCAL_SECRET, undefined)
  run.child.kill("SIGTERM")
})

test("a second signal while stopping waits for every child instead of leaving them running", { skip }, async (t) => {
  const run = startHeadless(t, { env: { FAKE_SLOW_STOP_MS: "1000" } })
  await run.ready
  const pids = Object.values(await recorded(run.log)).map((c) => c.pid)
  run.child.kill("SIGTERM")
  await new Promise((resolve) => setTimeout(resolve, 200))
  run.child.kill("SIGINT")
  assert.equal(await run.exited, 0)
  assert.deepEqual(pids.filter(alive), [])
})

test("with a Caddyfile it starts Caddy on the API's port, ChatGPT's callback port and the SPA", { skip }, async (t) => {
  const run = startHeadless(t, { caddy: true })
  const url = await run.ready
  const children = await recorded(run.log, 5)
  const caddy = children.caddy
  assert.ok(caddy, "caddy started")
  const caddyfile = join(run.dataDir, "..", "caddy", "Caddyfile")
  assert.deepEqual(caddy.args, ["run", "--config", caddyfile, "--adapter", "caddyfile"])
  assert.equal(caddy.cwd, join(run.dataDir, "..", "caddy"))
  assert.equal(caddy.caddy.SURFSENSE_API_PORT, new URL(url).port)
  assert.equal(caddy.caddy.SURFSENSE_FRONTEND_DIR, join(run.dataDir, "..", "dist"))
  // The API listens for ChatGPT where Caddy forwards `/callback`.
  assert.ok(Number(caddy.caddy.SURFSENSE_CHATGPT_CALLBACK_PORT) > 0)
  assert.equal(children.api?.chatgptCallbackPort, caddy.caddy.SURFSENSE_CHATGPT_CALLBACK_PORT)
  run.child.kill("SIGTERM")
  assert.equal(await run.exited, 0)
  assert.equal(alive(caddy.pid), false)
})

test("Caddy asks the access service, which answers on the port Caddy is given", { skip }, async (t) => {
  const run = startHeadless(t, { caddy: true })
  await run.ready
  const children = await recorded(run.log, 5)
  const port = children.caddy?.caddy.SURFSENSE_ACCESS_PORT
  assert.ok(Number(port) > 0)
  const state = await fetch(`http://127.0.0.1:${port}/access/state`, {
    headers: { "X-Forwarded-Host": "localhost:4929", "X-Forwarded-For": "127.0.0.1" },
  })
  assert.deepEqual(await state.json(), { password: false, signedIn: false, host: true })
  run.child.kill("SIGTERM")
  assert.equal(await run.exited, 0)
})

test("SURFSENSE_PASSWORD sets the password at start, and no sidecar sees it", { skip }, async (t) => {
  const run = startHeadless(t, { caddy: true, env: { SURFSENSE_PASSWORD: "correct horse battery" } })
  await run.ready
  const children = await recorded(run.log, 5)
  const port = children.caddy?.caddy.SURFSENSE_ACCESS_PORT
  const state = await fetch(`http://127.0.0.1:${port}/access/state`, {
    headers: { "X-Forwarded-Host": "localhost:4929", "X-Forwarded-For": "127.0.0.1" },
  })
  assert.equal(((await state.json()) as { password: boolean }).password, true)
  for (const child of Object.values(children)) assert.equal(child.env.SURFSENSE_PASSWORD, undefined)
  run.child.kill("SIGTERM")
  assert.equal(await run.exited, 0)
})

test("SURFSENSE_TLS=internal starts Caddy on its LAN configuration, for the allowed hosts", { skip }, async (t) => {
  const run = startHeadless(t, {
    caddy: true,
    env: { SURFSENSE_TLS: "internal", SURFSENSE_ALLOWED_HOSTS: "surfsense.lan", SURFSENSE_HTTPS_PORT: "4943" },
  })
  await run.ready
  const caddy = (await recorded(run.log, 5)).caddy
  assert.deepEqual(caddy?.args, ["run", "--config", join(run.dataDir, "..", "caddy", "Caddyfile.lan"), "--adapter", "caddyfile"])
  assert.equal(caddy?.caddy.SURFSENSE_TLS_SITES, "https://surfsense.lan")
  assert.equal(caddy?.caddy.SURFSENSE_HTTPS_PORT, "4943")
  run.child.kill("SIGTERM")
  assert.equal(await run.exited, 0)
})

test("SURFSENSE_DOMAIN tells the API its public domain, for plugin sign-ins there", { skip }, async (t) => {
  const run = startHeadless(t, { caddy: true, env: { SURFSENSE_DOMAIN: "surfsense.example.com" } })
  await run.ready
  const children = await recorded(run.log, 5)
  assert.equal(children.api?.env.SURFSENSE_LOCAL_DOMAIN, "surfsense.example.com")
  run.child.kill("SIGTERM")
  assert.equal(await run.exited, 0)
})

test("a TLS setting it cannot serve stops the container at start, saying why", { skip }, async (t) => {
  const run = startHeadless(t, { caddy: true, env: { SURFSENSE_TLS: "internal" } })
  // It never gets ready; that is the point.
  run.ready.catch(() => undefined)
  let stderr = ""
  run.child.stderr?.on("data", (chunk) => (stderr += chunk))
  assert.notEqual(await run.exited, 0)
  assert.match(stderr, /SURFSENSE_ALLOWED_HOSTS/)
  // Before anything started: no sidecar wrote a record.
  assert.deepEqual(readdirSync(run.log), [])
})

test("without a Caddyfile, as on a checkout, it starts no Caddy and fixes no callback port", { skip }, async (t) => {
  const run = startHeadless(t)
  await run.ready
  const children = await recorded(run.log)
  assert.equal(children.caddy, undefined)
  assert.equal(children.api?.chatgptCallbackPort, undefined)
  run.child.kill("SIGTERM")
})

test("Caddy exiting stops the rest and exits non-zero, since nothing can reach the app", { skip }, async (t) => {
  const run = startHeadless(t, { caddy: true, env: { FAKE_CADDY_EXIT_AFTER_MS: "700" } })
  await run.ready
  const pids = Object.values(await recorded(run.log, 5)).map((c) => c.pid)
  assert.notEqual(await run.exited, 0)
  assert.deepEqual(pids.filter(alive), [])
})
