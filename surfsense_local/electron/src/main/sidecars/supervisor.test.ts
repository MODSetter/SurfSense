import assert from "node:assert/strict"
import { existsSync, mkdtempSync, readFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { isWindows } from "./platform.ts"
import { startOne, stopNamed, type Sidecars } from "./supervisor.ts"
import type { SidecarSpec } from "./types.ts"

/** A sidecar that runs `script` under this Node, from a scratch folder. */
function nodeSidecar(name: string, script: string, env: Record<string, string>): SidecarSpec {
  return {
    name,
    cmd: process.execPath,
    args: ["-e", script],
    cwd: mkdtempSync(join(tmpdir(), "supervisor-")),
    env,
  }
}

/** Resolves once `path` exists, which the child writes when it is ready. */
async function written(path: string): Promise<string> {
  for (let tries = 0; tries < 200; tries++) {
    if (existsSync(path)) {
      const text = readFileSync(path, "utf8")
      if (text) return text
    }
    await new Promise((resolve) => setTimeout(resolve, 25))
  }
  throw new Error(`${path} was never written`)
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

test("a sidecar that does not inherit sees only its own variables", async () => {
  process.env.SURFSENSE_LOCAL_SECRET = "leaked"
  const out = join(mkdtempSync(join(tmpdir(), "supervisor-")), "env.json")
  const sidecars: Sidecars = new Map()
  try {
    startOne(sidecars, {
      ...nodeSidecar(
        "isolated",
        "require('fs').writeFileSync(process.env.OUT, JSON.stringify(process.env))",
        { OUT: out }
      ),
      inheritEnv: false,
    })
    const seen = JSON.parse(await written(out)) as Record<string, string>
    assert.equal(seen.SURFSENSE_LOCAL_SECRET, undefined)
    assert.equal(seen.OUT, out)
  } finally {
    delete process.env.SURFSENSE_LOCAL_SECRET
    await stopNamed(sidecars, "isolated")
  }
})

test(
  "stopping a sidecar takes down what it started, even after it has exited",
  { skip: isWindows && "Windows kills the tree with taskkill /t" },
  async () => {
    // A shell command the agent ran can outlive opencode, which exits on SIGTERM.
    const folder = mkdtempSync(join(tmpdir(), "supervisor-"))
    const pidFile = join(folder, "grandchild.pid")
    // Written only once SIGTERM is ignored, so the stop below cannot race it.
    const stubborn = [
      "process.on('SIGTERM', () => {})",
      "require('fs').writeFileSync(process.env.PID_FILE, String(process.pid))",
      "setInterval(() => {}, 1000)",
    ].join("\n")
    const parent = [
      "const { spawn } = require('child_process')",
      `spawn(process.execPath, ['-e', ${JSON.stringify(stubborn)}], { stdio: 'ignore' })`,
      "process.on('SIGTERM', () => process.exit(0))",
      "setInterval(() => {}, 1000)",
    ].join("\n")
    const sidecars: Sidecars = new Map()
    startOne(sidecars, nodeSidecar("parent", parent, { PID_FILE: pidFile }))
    const grandchild = Number(await written(pidFile))

    await stopNamed(sidecars, "parent")
    await new Promise((resolve) => setTimeout(resolve, 200)) // let the OS reap it

    assert.equal(isAlive(grandchild), false)
  }
)
