import type { ChatMode } from "@/features/models/capability/api"
import type { ModelSelection } from "@/features/models/selection/api"

import { agenticReasonText, agenticReasonWarns } from "./mode-text"
import { useChatModes } from "./new-chat-mode"

/**
 * Under a new chat's composer once Agentic is picked: the model's score, the
 * untested warning, or the note on a local copy. A model that passed says nothing.
 */
export function AgenticNote({
  model,
  mode,
}: {
  model: ModelSelection | null
  mode: ChatMode | null
}) {
  const modes = useChatModes(model)
  if (mode !== "agentic" || !modes || !agenticReasonWarns(modes.reason)) {
    return null
  }
  return (
    <p
      role="status"
      className="mt-1 px-2 text-[11px] text-muted-foreground select-none"
    >
      {agenticReasonText(modes.reason)}
    </p>
  )
}
