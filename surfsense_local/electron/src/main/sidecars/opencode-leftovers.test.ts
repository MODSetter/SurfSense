import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { existsSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { getFreePort } from "../net.ts"
import { recordOpencode, stopLeftoverOpencode } from "./opencode-leftovers.ts"
import { isWindows } from "./platform.ts"

const HOST = "127.0.0.1"

// Answers as `serve` does, and only with the right password: 1.x on its health
// route, 2.x with its pid on /api/info, which answers 503 while it boots.
const FAKE_SERVE = `
const http = require("http")
const expected = "Basic " + Buffer.from("opencode:" + process.env.PASSWORD).toString("base64")
const route = process.env.RELEASE === "1" ? "/global/health" : "/api/info"
const pid = process.env.REPORTED_PID ? Number(process.env.REPORTED_PID) : process.pid
http.createServer((request, response) => {
  if (request.headers.authorization !== expected) { response.writeHead(401); return response.end() }
  if (request.url !== route) { response.writeHead(404); return response.end() }
  response.writeHead(Number(process.env.STATUS || 200), { "content-type": "application/json" })
  response.end(JSON.stringify(process.env.RELEASE === "1" ? { healthy: true, version: "1.18.34" } : { version: "2.1.2", pid }))
}).listen(Number(process.env.PORT), "${HOST}", () => console.log("ready"))
`

/** A process left running, as `serve` is when the app that started it crashes. */
async function leftover(env: Record<string, string>): Promise<number> {
  const child = spawn(process.execPath, ["-e", FAKE_SERVE], {
    env: { ...process.env, ...env },
    detached: true,
    stdio: ["ignore", "pipe", "ignore"],
  })
  await new Promise((resolve) => child.stdout!.once("data", resolve))
  child.unref()
  return child.pid!
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

/** Record a leftover started with `env`, run the boot's sweep, and say whether it survived. */
async function survives(env: Record<string, string>): Promise<boolean> {
  const agentDir = mkdtempSync(join(tmpdir(), "leftovers-"))
  const port = await getFreePort(HOST)
  const pid = await leftover({ PORT: String(port), PASSWORD: "old-launch", ...env })
  try {
    recordOpencode(agentDir, { pid, port, password: "old-launch" }) // pragma: allowlist secret
    await stopLeftoverOpencode(agentDir, HOST)
    await new Promise((resolve) => setTimeout(resolve, 200)) // let the OS reap it
    return isAlive(pid)
  } finally {
    if (isAlive(pid)) process.kill(isWindows ? pid : -pid, "SIGKILL")
  }
}

test("stops an opencode a crashed run left, once it names the recorded process", async () => {
  assert.equal(await survives({}), false)
})

test("stops one that crashed while still booting", async () => {
  // 2.x answers /api/info with its pid even before it is ready.
  assert.equal(await survives({ STATUS: "503" }), false)
})

test("leaves a server alone that is some other process", async () => {
  // Port and password may be reused by the time of the next boot; the pid must match too.
  assert.equal(await survives({ REPORTED_PID: "1" }), true)
})

test("still stops a 1.x opencode left by the release before", async () => {
  assert.equal(await survives({ RELEASE: "1" }), false)
})

test("leaves a process alone when the record no longer opens it", async () => {
  // The pid may belong to anything by now; only the password proves identity.
  const agentDir = mkdtempSync(join(tmpdir(), "leftovers-"))
  const port = await getFreePort(HOST)
  const pid = await leftover({ PORT: String(port), PASSWORD: "someone-else" })
  try {
    recordOpencode(agentDir, { pid, port, password: "old-launch" }) // pragma: allowlist secret

    await stopLeftoverOpencode(agentDir, HOST)

    assert.equal(isAlive(pid), true)
    assert.equal(existsSync(join(agentDir, "opencode-process.json")), false)
  } finally {
    // Windows has no process groups, and the fake has no children to reach.
    process.kill(isWindows ? pid : -pid, "SIGKILL")
  }
})
