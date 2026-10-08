import assert from "node:assert/strict"
import test from "node:test"
import { setFlagsFromString } from "node:v8"
import { runInNewContext } from "node:vm"

import { createSessionLog } from "./session-log.ts"
import { warnMain } from "./main-warn.ts"

const at = () => new Date(2026, 8, 25, 18, 21, 3)

test("a main warning goes to the terminal and the log tagged as main", () => {
  const log = createSessionLog({ home: "/home/ada", now: at })
  const written: string[] = []
  const original = process.stderr.write
  process.stderr.write = ((chunk: string) => {
    written.push(chunk)
    return true
  }) as typeof process.stderr.write
  try {
    warnMain(log, "failed to save theme preference: boom")
  } finally {
    process.stderr.write = original
  }

  assert.deepEqual(written, ["[main] failed to save theme preference: boom\n"])
  assert.deepEqual(log.lines(), [
    "18:21:03 [main] failed to save theme preference: boom",
  ])
})

test("prefixes every line with the time and the process that wrote it", () => {
  const log = createSessionLog({ home: "/home/ada", now: at })

  log.append("api", "Started server process\nWaiting for application startup.")

  assert.deepEqual(log.lines(), [
    "18:21:03 [api] Started server process",
    "18:21:03 [api] Waiting for application startup.",
  ])
})

test("keeps only the newest lines", () => {
  const log = createSessionLog({ home: "/home/ada", now: at, maxLines: 2 })

  for (const n of [1, 2, 3]) log.append("api", `line ${n}`)

  assert.deepEqual(log.lines(), [
    "18:21:03 [api] line 2",
    "18:21:03 [api] line 3",
  ])
})

test("replaces the home directory however a Windows path is spelled", () => {
  const log = createSessionLog({ home: "C:\\Users\\ada", now: at })

  log.append("worker-ingest", "opened C:\\Users\\ada\\.surfsense\\surfsense.db")
  log.append("worker-ingest", "opened C:/Users/ada/.surfsense/huey.db")
  log.append("worker-ingest", "models in 'C:\\\\Users\\\\ada\\\\.surfsense\\\\models'")

  assert.deepEqual(log.lines(), [
    "18:21:03 [worker-ingest] opened ~\\.surfsense\\surfsense.db",
    "18:21:03 [worker-ingest] opened ~/.surfsense/huey.db",
    "18:21:03 [worker-ingest] models in '~\\\\.surfsense\\\\models'",
  ])
})

test("drops colour codes and successful polling, and keeps failures and writes", () => {
  const log = createSessionLog({ home: "/home/ada", now: at })

  log.append("llamacpp", "\u001b[32mserver is listening\u001b[0m")
  log.append(
    "api",
    'INFO:     127.0.0.1:60312 - "GET /llm/image/local/runtime HTTP/1.1" 200 OK'
  )
  log.append(
    "api",
    'INFO:     127.0.0.1:60313 - "GET /workspaces/1/documents/9 HTTP/1.1" 404 Not Found'
  )
  log.append("api", 'INFO:     127.0.0.1:60314 - "POST /chat HTTP/1.1" 200 OK')

  assert.deepEqual(log.lines(), [
    "18:21:03 [llamacpp] server is listening",
    '18:21:03 [api] INFO:     127.0.0.1:60313 - "GET /workspaces/1/documents/9 HTTP/1.1" 404 Not Found',
    '18:21:03 [api] INFO:     127.0.0.1:60314 - "POST /chat HTTP/1.1" 200 OK',
  ])
})

test("a kept line holds only its own text, not the text it was cut from", () => {
  setFlagsFromString("--expose-gc")
  const gc = runInNewContext("gc") as () => void
  const log = createSessionLog({ home: "/home/ada", now: at })
  gc()
  const before = process.memoryUsage().heapUsed

  // 50 MB of output, of which the log keeps 2,000 characters a line.
  for (let n = 0; n < 50; n++) log.append("api", `WARNING ${n} ${"x".repeat(1 << 20)}`)
  gc()
  const held = process.memoryUsage().heapUsed - before

  assert.ok(held < 10 * 1024 * 1024, `the log held ${(held / 1048576).toFixed(1)} MB`)
  assert.equal(log.lines().length, 50)
  for (const line of log.lines()) {
    assert.ok(line.endsWith("…"))
    assert.ok(line.length <= "18:21:03 [api] ".length + 2001)
  }
})
