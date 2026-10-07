import { createContext, useContext } from "react"

import type { ChatMode } from "@/features/models/capability/api"
import {
  modelKey,
  type ModelSelection,
  type SelectionTarget,
} from "@/features/models/selection/api"

export type NewChatModePicks = {
  // Per model, the mode picked this session; the API remembers it once a chat opens in it.
  picks: Readonly<Record<string, ChatMode>>
  pick: (model: SelectionTarget, mode: ChatMode) => void
}

// Without a provider, nothing is picked and the model's own default holds.
export const NewChatModeContext = createContext<NewChatModePicks>({
  picks: {},
  pick: () => undefined,
})

/**
 * The mode the next new chat starts in: the one picked for this model, else
 * its default. Null for a model that reports no modes.
 */
export function resolveNewChatMode(
  model: ModelSelection | null,
  picks: NewChatModePicks["picks"]
): ChatMode | null {
  const modes = model?.capability?.modes
  if (!model || !modes) return null
  const wanted = picks[modelKey(model)] ?? modes.default_mode
  return wanted === "agentic" && !modes.agentic_allowed ? "basic" : wanted
}

export function useNewChatMode(model: ModelSelection | null) {
  return resolveNewChatMode(model, useContext(NewChatModeContext).picks)
}

export function usePickNewChatMode() {
  return useContext(NewChatModeContext).pick
}
