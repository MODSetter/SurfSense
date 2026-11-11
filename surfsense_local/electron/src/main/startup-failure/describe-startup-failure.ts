// A Python traceback ends with the error, so its last lines say what went wrong.
const API_TAIL_LINES = 3

export type StartupFailure = { title: string; detail: string }

/**
 * What the dialog says when the API did not start: why Electron gave up, and
 * the last of the API's own output, where a refused migration or a full disk
 * is named. `logLines` is the session log, oldest first.
 */
export function describeStartupFailure(
  error: unknown,
  logLines: readonly string[]
): StartupFailure {
  const reason = error instanceof Error ? error.message : String(error)
  const apiTail = logLines
    .filter((line) => line.includes(" [api] "))
    .slice(-API_TAIL_LINES)
    .map((line) => line.slice(line.indexOf(" [api] ") + " [api] ".length))
  const parts = [reason]
  if (apiTail.length > 0) {
    parts.push(`The API's last output:\n${apiTail.join("\n")}`)
  }
  parts.push(
    "Start SurfSense again. If it keeps failing, include this message in a report."
  )
  return { title: "SurfSense could not start", detail: parts.join("\n\n") }
}
