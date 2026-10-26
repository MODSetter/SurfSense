import assert from "node:assert/strict"
import test from "node:test"

import { createSessionLog } from "../../../../sidecars/session-log/session-log.ts"
import { updaterLogger } from "./updater-log.ts"

test("electron-updater's lines reach the session log without its staging ID", () => {
  const log = createSessionLog({ home: "/home/ada", now: () => new Date(0) })
  const logger = updaterLogger(log)

  logger.info(
    "Staging percentage: 0.5, percentage: 0.1, user id: 7c1f0a52-3b8e-4c1d-9f2e-0a6b5c4d3e2f"
  )
  logger.error("Error: net::ERR_INTERNET_DISCONNECTED")

  const lines = log.lines()
  assert.equal(lines.length, 2)
  assert.match(lines[0]!, /\[updater\] Staging percentage: 0\.5, percentage: 0\.1, user id: <id>$/)
  assert.match(lines[1]!, /\[updater\] Error: net::ERR_INTERNET_DISCONNECTED$/)
})
