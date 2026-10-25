import { ApiError } from "@/lib/api"

// What the dialog shows in place of results when a search or an add fails.
export type WebProblem =
  | { kind: "license"; reason: string }
  | { kind: "unreachable" }
  | { kind: "search_failed" }
  | { kind: "network_off" }
  | { kind: "failed" }

export function webProblem(cause: unknown): WebProblem {
  if (!(cause instanceof ApiError)) return { kind: "failed" }
  if (cause.code === "license_refused") {
    const reason = cause.detail.reason
    return {
      kind: "license",
      reason: typeof reason === "string" ? reason : "missing_license",
    }
  }
  if (cause.code === "plugin_unavailable") return { kind: "unreachable" }
  if (cause.code === "plugin_refused") return { kind: "search_failed" }
  // Still refused after the prompt: the user said no.
  if (cause.code === "egress_disabled") return { kind: "network_off" }
  return { kind: "failed" }
}
