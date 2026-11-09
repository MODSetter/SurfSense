import { ApiError } from "@/lib/api"

/**
 * Why the user's own OAuth app is asked for: the provider registers no app, it refused
 * SurfSense, or the user chose one, as an organisation allowing only its approved app does.
 */
export type OwnAppReason = "needs_client" | "refused" | "chosen"

/** The reason a refusal gives, or null for one the user's own app would not answer. */
export function ownAppReason(refused: unknown): OwnAppReason | null {
  if (!(refused instanceof ApiError)) return null
  if (refused.code === "plugin_oauth_needs_client") return "needs_client"
  if (refused.code === "plugin_oauth_refused") return "refused"
  return null
}
