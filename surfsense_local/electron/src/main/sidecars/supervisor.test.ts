import assert from "node:assert/strict"
import { once } from "node:events"
import { WriteStream, existsSync, mkdtempSync, readFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Writable } from "node:stream"
import test from "node:test"

import { sessionLog } from "../session-log/session-log.ts"
import { isWindows } from "./platform.ts"
import { createEcho, startOne, stopNamed, terminal, type Sidecars } from "./supervisor.ts"
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

test("a sidecar's output is mirrored under its name and logged line by line", async () => {
  const echoed: [1 | 2, string][] = []
  const sidecars: Sidecars = new Map()
  startOne(
    sidecars,
    nodeSidecar(
      "mirrored",
      "process.stdout.write('one\\ntwo\\n'); process.stderr.write('three\\n')",
      {},
    ),
    undefined,
    (fd, text) => echoed.push([fd, text]),
  )
  const child = sidecars.get("mirrored")
  assert.ok(child)
  await once(child, "close")
  await new Promise((resolve) => setImmediate(resolve))

  // Each read is mirrored whole under the name.
  const mirrored = (to: 1 | 2) =>
    echoed
      .filter(([fd]) => fd === to)
      .map(([, text]) => {
        assert.ok(text.startsWith("[mirrored] "))
        return text.slice("[mirrored] ".length)
      })
  assert.equal(mirrored(1).join(""), "one\ntwo\n")
  assert.deepEqual(mirrored(2), ["three\n"])
  const logged = sessionLog
    .lines()
    .filter((line) => line.includes(" [mirrored] "))
    .map((line) => line.slice(line.indexOf("[mirrored]")))
  assert.deepEqual(logged.sort(), [
    "[mirrored] crashed (code=0 signal=null)",
    "[mirrored] one",
    "[mirrored] three",
    "[mirrored] two",
  ])
})

/** A terminal that has stopped reading: nothing written ever completes. */
function stalledTerminal(): Writable {
  return new Writable({ write: () => {} })
}

test("a terminal that stops reading holds no more than 1 MB of mirrored output", () => {
  const terminal = stalledTerminal()
  const echo = createEcho(() => terminal)
  const line = `[api] INFO:     127.0.0.1:60313 - "POST /chat HTTP/1.1" 200 OK ${"x".repeat(950)}\n`

  for (let n = 0; n < 3000; n++) echo(1, line)

  assert.ok(terminal.writableLength <= (1 << 20) + line.length)
  assert.ok(terminal.writableLength >= (1 << 20) - line.length)
})

test("a terminal that went away stops the mirror and does not crash", async () => {
  let writes = 0
  const gone = new Writable({
    write: (_chunk, _encoding, done) => {
      writes++
      done(Object.assign(new Error("write EPIPE"), { code: "EPIPE" }))
    },
  })
  const echo = createEcho(() => gone)

  echo(2, "[api] first\n")
  await new Promise((resolve) => setImmediate(resolve))
  echo(2, "[api] second\n")
  echo(2, "[api] third\n")

  assert.equal(writes, 1)
})

test("off Windows the mirror writes through Node's own stdout and stderr", () => {
  // Node queues a full pipe there; an fs stream would fail on its non-blocking
  // mode after a few tries, and the mirror would stop for the rest of the run.
  assert.equal(terminal(1, false), process.stdout)
  assert.equal(terminal(2, false), process.stderr)
})

test("on Windows the mirror writes from libuv's pool, not through process.stdout", () => {
  const stream = terminal(2, true)

  assert.ok(stream instanceof WriteStream)
  assert.equal(Reflect.get(stream, "fd"), 2)
})

test("a sidecar's exit note is written before the app can exit", async () => {
  // shutdown() exits the app right after the last sidecar's `exit`, which
  // would discard a note still queued behind the mirror.
  const written: string[] = []
  const write = process.stderr.write
  process.stderr.write = ((chunk: string | Uint8Array) => {
    written.push(String(chunk))
    return true
  }) as typeof process.stderr.write
  let atExit: string[] = []
  try {
    const sidecars: Sidecars = new Map()
    startOne(sidecars, nodeSidecar("noted", "", {}), undefined, createEcho(stalledTerminal))
    const child = sidecars.get("noted")
    assert.ok(child)
    child.on("exit", () => {
      atExit = written.filter((text) => text.startsWith("[noted] "))
    })
    await once(child, "close")
  } finally {
    process.stderr.write = write
  }

  assert.deepEqual(atExit, ["[noted] crashed (code=0 signal=null)\n"])
})

test("an echo with no terminal to open stays silent", () => {
  const echo = createEcho(() => {
    throw new Error("EBADF: bad file descriptor")
  })

  assert.doesNotThrow(() => {
    echo(1, "[api] started\n")
    echo(1, "[api] still running\n")
  })
})
