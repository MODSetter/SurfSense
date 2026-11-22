import type { SessionLog } from "../../../../sidecars/session-log/session-log.ts"

// electron-updater logs its local staging ID ("user id: <uuid>"); the session
// log is pasted into public issues, so no UUID gets through.
const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi

/** electron-updater's logger: the session log, since a packaged app shows no console. */
export function updaterLogger(log: SessionLog) {
  const write = (message: unknown) =>
    log.append("updater", String(message).replace(UUID, "<id>"))
  return { info: write, warn: write, error: write }
}
