import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { existsSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { getFreePort } from "../net.ts"
import { recordOpencode, stopLeftoverOpencode } from "./opencode-leftovers.ts"

const HOST = "127.0.0.1"

// Answers opencode's health route, and only with the right password, as `serve` does.
const FAKE_SERVE = `
const http = require("http")
const expected = "Basic " + Buffer.from("opencode:" + process.env.PASSWORD).toString("base64")
http.createServer((request, response) => {
  if (request.headers.authorization !== expected) { response.writeHead(401); return response.end() }
  response.writeHead(200, { "content-type": "application/json" })
  response.end(JSON.stringify({ healthy: true, version: "1.18.34" }))
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

test("stops an opencode a crashed run left, once its password proves it is ours", async () => {
  const agentDir = mkdtempSync(join(tmpdir(), "leftovers-"))
  const port = await getFreePort(HOST)
  const pid = await leftover({ PORT: String(port), PASSWORD: "old-launch" })
  recordOpencode(agentDir, { pid, port, password: "old-launch" })

  await stopLeftoverOpencode(agentDir, HOST)
  await new Promise((resolve) => setTimeout(resolve, 200)) // let the OS reap it

  assert.equal(isAlive(pid), false)
})

test("leaves a process alone when the record no longer opens it", async () => {
  // The pid may belong to anything by now; only the password proves identity.
  const agentDir = mkdtempSync(join(tmpdir(), "leftovers-"))
  const port = await getFreePort(HOST)
  const pid = await leftover({ PORT: String(port), PASSWORD: "someone-else" })
  try {
    recordOpencode(agentDir, { pid, port, password: "old-launch" })

    await stopLeftoverOpencode(agentDir, HOST)

    assert.equal(isAlive(pid), true)
    assert.equal(existsSync(join(agentDir, "opencode-process.json")), false)
  } finally {
    process.kill(-pid, "SIGKILL")
  }
})
