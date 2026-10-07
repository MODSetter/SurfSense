import { createContext, useContext, useMemo } from "react"

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

/**
 * The mode the next new chat opens in, and whether the user chose it. Only a
 * choice is remembered: a default sent back as one would outlast its score.
 */
export type NewChatChoice = { mode: ChatMode; chosen: boolean }

// Without a provider, nothing is picked and the model's own default holds.
export const NewChatModeContext = createContext<NewChatModePicks>({
  picks: {},
  pick: () => undefined,
})

/**
 * The mode the next new chat starts in: the one picked for this model, else
 * its default. Null for a model that reports no modes.
 */
export function resolveNewChatChoice(
  model: ModelSelection | null,
  picks: NewChatModePicks["picks"]
): NewChatChoice | null {
  const modes = model?.capability?.modes
  if (!model || !modes) return null
  const picked = picks[modelKey(model)]
  const wanted = picked ?? modes.default_mode
  const mode = wanted === "agentic" && !modes.agentic_allowed ? "basic" : wanted
  return { mode, chosen: picked === mode }
}

export function useNewChatChoice(model: ModelSelection | null) {
  const choice = resolveNewChatChoice(
    model,
    useContext(NewChatModeContext).picks
  )
  const mode = choice?.mode ?? null
  const chosen = choice?.chosen ?? false
  // Held while it says the same, so the runtime's send is not made anew.
  return useMemo<NewChatChoice | null>(
    () => (mode ? { mode, chosen } : null),
    [mode, chosen]
  )
}

export function useNewChatMode(model: ModelSelection | null) {
  return useNewChatChoice(model)?.mode ?? null
}

export function usePickNewChatMode() {
  return useContext(NewChatModeContext).pick
}
