import { ApiError } from "@/lib/api"

// What the dialog shows above its rows when a search or an add fails.
export type WebProblem =
  | { kind: "search_unreachable"; host: string }
  | { kind: "search_failed"; host: string }
  | { kind: "network_off"; hosts: string[] }
  | { kind: "failed" }

export function webProblem(cause: unknown): WebProblem {
  if (!(cause instanceof ApiError)) return { kind: "failed" }
  const host = typeof cause.detail.host === "string" ? cause.detail.host : ""
  if (cause.code === "search_unreachable") {
    return { kind: "search_unreachable", host }
  }
  if (cause.code === "search_failed") return { kind: "search_failed", host }
  // Still refused after the prompt: the user said no.
  if (cause.code === "egress_disabled") {
    const hosts = Array.isArray(cause.detail.hosts)
      ? cause.detail.hosts.filter((h): h is string => typeof h === "string")
      : []
    return { kind: "network_off", hosts: hosts.length ? hosts : [host] }
  }
  return { kind: "failed" }
}
