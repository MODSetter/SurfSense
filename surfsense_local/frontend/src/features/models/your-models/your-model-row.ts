import { intl } from "@/i18n/intl"

import type { Connection } from "../remote/connections/api"
import type { ModelSelection, SelectionTarget } from "../selection/api"

/** One model on this computer that can fill a slot. */
export type YourModelRow = {
  key: string
  name: string
  selected: boolean
  badges: string[]
  /** Said under the name: why it cannot run, or that it is starting. */
  note: string | null
  /** Null when it cannot fill this slot. */
  target: SelectionTarget | null
  /** What deletion acts on; null when it cannot be deleted from here. */
  removeId: string | null
}

/** The model filling a slot, named the way the list names it. */
export type InUse = {
  name: string
  source: string
  /** Where it runs, for copy that phrases the source rather than naming it. */
  where: "local" | "server" | "missing"
}

export type YourModels = {
  /** Models on this computer. Server models are listed per server instead. */
  local: YourModelRow[]
  inUse: InUse | null
  isPending: boolean
  error: Error | null
  /** False where this computer cannot run the slot's models itself. */
  canDownload: boolean
}

/**
 * A local model's own row names it best; a server model is named by its id and
 * its server. A local selection no row answers to is still named, not hidden.
 */
export function describeInUse(
  selection: ModelSelection | null | undefined,
  local: YourModelRow[],
  connections: Connection[] | undefined
): InUse | null {
  if (!selection) return null
  if (selection.provider === "openai_compatible") {
    const server = connections?.find(({ id }) => id === selection.connection_id)
    return {
      name: selection.name,
      source:
        server?.label ??
        intl.formatMessage({
          id: "models_in_use_unknown_server_label",
          defaultMessage: "A server",
        }),
      where: "server",
    }
  }
  const row = local.find((candidate) => candidate.selected)
  return row
    ? {
        name: row.name,
        source: intl.formatMessage({
          id: "models_in_use_local_label",
          defaultMessage: "This computer",
        }),
        where: "local",
      }
    : {
        name: selection.name,
        source: intl.formatMessage({
          id: "models_in_use_missing_label",
          defaultMessage: "Not found on this computer",
        }),
        where: "missing",
      }
}
