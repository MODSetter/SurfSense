import assert from "node:assert/strict"
import test from "node:test"

import { createSessionLog } from "./session-log.ts"

const at = () => new Date(2026, 8, 25, 18, 21, 3)

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
