import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"
import { modelKey, type ModelSelection } from "@/features/models/selection/api"

/** Why a chat model could not be confirmed: the API's error code. */
export type ModelIssue = {
  // Connection and name, so a same-named model elsewhere is not blamed.
  key: string
  model: string
  code: string | null
  // What egress refused, for `egress_disabled`.
  destination?: string | null
  host?: string | null
}

const EGRESS_OFF = "egress_disabled"

// Egress off is a consent not yet given, not a broken model: the model stays
// selected, and the notice asks for it before any message is sent.
export function asksOnSend(error: unknown): boolean {
  return error instanceof ApiError && error.code === EGRESS_OFF
}

export function issueAsksOnSend(issue: ModelIssue): boolean {
  return issue.code === EGRESS_OFF
}

export function isIssueFor(
  issue: ModelIssue,
  selection: ModelSelection | null
): boolean {
  return selection !== null && modelKey(selection) === issue.key
}

export function modelIssueFrom(
  selection: ModelSelection,
  error: unknown
): ModelIssue {
  const identity = { key: modelKey(selection), model: selection.name }
  if (!(error instanceof ApiError)) return { ...identity, code: null }
  const text = (value: unknown) => (typeof value === "string" ? value : null)
  return {
    ...identity,
    code: error.code,
    destination: text(error.detail.destination),
    host: text(error.detail.host),
  }
}

// The composer's placeholder while egress holds it: the notice above says why.
export function blockedPlaceholder(issue: ModelIssue): string {
  return intl.formatMessage(
    {
      id: "chat_composer_egress_off_placeholder",
      defaultMessage: "Allow sending to {host} to chat",
    },
    { host: issue.host ?? issue.model }
  )
}
