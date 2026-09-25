import { ApiError } from "@/lib/api"
import { getProviderModels } from "@/features/models/chat-candidates/api"
import { getConnectionModels } from "@/features/models/remote/models/api"

import type { ModelSelection } from "./api"

/** Why the saved chat model can't be used, from the API's error code. */
export type ModelIssue = {
  model: string
  code: string | null
  // What egress refused, for `egress_disabled`.
  destination?: string | null
  host?: string | null
}

/**
 * Whether the saved chat model can be used. The one answer startup and the
 * dashboard share, so a status never drifts from a second copy of the rule.
 */
export type Availability =
  | { status: "checking" }
  | { status: "available" }
  // Gone from its list: nothing failed, so there is nothing to explain.
  | { status: "gone" }
  // Egress to its host is off: a consent not yet given, asked for up front.
  | { status: "needs-consent"; issue: ModelIssue }
  // An unreadable or rejected key, an unreachable endpoint, or anything else.
  | { status: "unusable"; issue: ModelIssue }

const EGRESS_OFF = "egress_disabled"

export async function checkAvailability(
  selection: ModelSelection,
  signal?: AbortSignal
): Promise<Availability> {
  try {
    return (await isListed(selection, signal))
      ? { status: "available" }
      : { status: "gone" }
  } catch (error) {
    const issue = issueFrom(selection, error)
    return issue.code === EGRESS_OFF
      ? { status: "needs-consent", issue }
      : { status: "unusable", issue }
  }
}

async function isListed(
  selection: ModelSelection,
  signal?: AbortSignal
): Promise<boolean> {
  if (selection.provider === "openai_compatible") {
    if (selection.connection_id === null) return false
    const models = await getConnectionModels(selection.connection_id, signal)
    return models.some((model) => model.name === selection.name)
  }
  const models = await getProviderModels(selection.provider, signal)
  return models.some(
    (model) =>
      model.installed &&
      model.selectable_for.includes("text_gen") &&
      model.name === selection.name
  )
}

function issueFrom(selection: ModelSelection, error: unknown): ModelIssue {
  if (!(error instanceof ApiError)) return { model: selection.name, code: null }
  const text = (value: unknown) => (typeof value === "string" ? value : null)
  return {
    model: selection.name,
    code: error.code,
    destination: text(error.detail.destination),
    host: text(error.detail.host),
  }
}
