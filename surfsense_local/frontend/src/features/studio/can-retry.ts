import type { Artifact } from "./api"

// How the backend starts the reason of a run its document script failed.
const SCRIPT_ERROR = "Script error: "

/** Whether running this version again could finish it. A script that failed
 *  would fail the same way; its agent renders the fix as the next version. A
 *  run stopped from outside, such as by the app closing, can run again. */
export function canRetry(artifact: Artifact): boolean {
  if (artifact.status === "cancelled") return true
  if (artifact.status !== "failed") return false
  return !(
    artifact.spec_kind === "python" &&
    (artifact.error_message ?? "").startsWith(SCRIPT_ERROR)
  )
}
