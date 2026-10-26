import assert from "node:assert/strict"
import { spawn, type ChildProcess } from "node:child_process"
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test, type TestContext } from "node:test"
import { fileURLToPath } from "node:url"

const MAIN = fileURLToPath(new URL("main.ts", import.meta.url))

// Stands in for the backend's venv Python: `main.py` serves /health, `worker.py`
// idles, and each records its pid and the environment it was given.
const FAKE_PYTHON = `#!/usr/bin/env node
const fs = require("node:fs")
const http = require("node:http")
const path = require("node:path")
const [entry, queue] = process.argv.slice(2)
const role = entry === "main.py" ? "api" : "worker-" + queue
const keys = ["HF_HUB_OFFLINE", "SURFSENSE_LOCAL_SIGNED_REGISTRY", "SURFSENSE_LOCAL_RUNTIME", "HOME", "SURFSENSE_LOCAL_SECRET", "SURFSENSE_LOCAL_DATA_DIR"]
fs.writeFileSync(path.join(process.env.FAKE_LOG, role + ".json"),
  JSON.stringify({ pid: process.pid, env: Object.fromEntries(keys.map((k) => [k, process.env[k]])) }))
if (role === "api") {
  http.createServer((req, res) => res.writeHead(req.url === "/health" ? 200 : 404).end())
    .listen(Number(process.env.SURFSENSE_LOCAL_PORT), process.env.SURFSENSE_LOCAL_HOST)
  const after = Number(process.env.FAKE_API_EXIT_AFTER_MS)
  if (after) setTimeout(() => process.exit(3), after)
} else {
  setInterval(() => {}, 1000)
}
`

interface Run {
  child: ChildProcess
  dataDir: string
  log: string
  exited: Promise<number | null>
  ready: Promise<string>
}

function startHeadless(t: TestContext, extraEnv: Record<string, string> = {}): Run {
  const root = mkdtempSync(join(tmpdir(), "surfsense-headless-"))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const backend = join(root, "backend")
  mkdirSync(join(backend, ".venv", "bin"), { recursive: true })
  const python = join(backend, ".venv", "bin", "python")
  writeFileSync(python, FAKE_PYTHON)
  chmodSync(python, 0o755)
  const dataDir = join(root, "data")
  const log = join(root, "log")
  mkdirSync(log)
  mkdirSync(join(root, "runtimes"))

  const child = spawn(process.execPath, [MAIN], {
    env: {
      ...process.env,
      SURFSENSE_LOCAL_BACKEND_DIR: backend,
      SURFSENSE_LOCAL_DATA_DIR: dataDir,
      SURFSENSE_LOCAL_MODELS_DIR: join(root, "models"),
      SURFSENSE_LOCAL_RUNTIMES_DIR: join(root, "runtimes"),
      SURFSENSE_LOCAL_SECRET: "",
      FAKE_LOG: log,
      ...extraEnv,
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

function recorded(log: string): Record<string, { pid: number; env: Record<string, string | undefined> }> {
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

  const children = recorded(run.log)
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
    const pids = Object.values(recorded(run.log)).map((c) => c.pid)
    run.child.kill(signal)
    assert.equal(await run.exited, 0)
    assert.deepEqual(pids.filter(alive), [])
    assert.equal(existsSync(join(run.dataDir, "api-url")), false)
  })
}

test("the API exiting stops the rest and exits non-zero, so the container restarts", { skip }, async (t) => {
  const run = startHeadless(t, { FAKE_API_EXIT_AFTER_MS: "700" })
  await run.ready
  const pids = Object.values(recorded(run.log)).map((c) => c.pid)
  assert.notEqual(await run.exited, 0)
  assert.deepEqual(pids.filter(alive), [])
})
