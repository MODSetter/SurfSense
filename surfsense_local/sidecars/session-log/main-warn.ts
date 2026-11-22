import type { SessionLog } from "./session-log.ts"

/**
 * A warning from the main process itself: the terminal in development, and
 * the session log so Report issue carries it. The source is always "main";
 * callers pass the text without a prefix.
 */
export function warnMain(log: SessionLog, text: string): void {
  process.stderr.write(`[main] ${text}\n`)
  log.append("main", text)
}
