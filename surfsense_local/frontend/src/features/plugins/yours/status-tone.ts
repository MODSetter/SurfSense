import type { Plugin } from "../api"

/** `failure`: something broke. `warning`: nothing broke, it needs a step from the user.
 * `idle`: off on purpose. `ok`: working. */
export type StatusTone = "failure" | "warning" | "idle" | "ok"

export const TONE_CLASS: Record<StatusTone, string> = {
  failure: "text-destructive",
  warning: "text-warning",
  idle: "text-muted-foreground",
  ok: "text-foreground",
}

/** A failed check's tone: a server down or a key or license refused is a failure; a sign-in,
 * more access, an OAuth app or a license to add or renew is a step to take. A plugin never
 * signed in is only not connected yet. */
export function checkTone(plugin: Plugin): Exclude<StatusTone, "ok"> {
  if (plugin.never_signed_in && !plugin.needs_own_app) return "idle"
  switch (plugin.check_failure) {
    case "unreachable":
    case "license_revoked":
    case "license_invalid":
      return "failure"
    case "sign_in":
      // A key the server refused is broken; an account to sign in with is a step.
      return plugin.auth_type === "oauth" ? "warning" : "failure"
    default:
      return "warning"
  }
}
