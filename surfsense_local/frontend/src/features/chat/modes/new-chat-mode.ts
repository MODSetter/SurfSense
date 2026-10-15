import { createContext, useContext, useMemo } from "react"

import type { ChatMode, ChatModes } from "@/features/models/capability/api"
import {
  modelKey,
  type ModelSelection,
  type SelectionTarget,
} from "@/features/models/selection/api"

export type NewChatModePicks = {
  // Per model, the mode picked this session; the API remembers it once a chat opens in it.
  picks: Readonly<Record<string, ChatMode>>
  pick: (model: SelectionTarget, mode: ChatMode) => void
  // Per model, the gate the API refused an Agentic chat with this session: a
  // local model's tool calls and window are read only when a chat starts.
  blocks: Readonly<Record<string, string>>
  block: (model: SelectionTarget, gate: string) => void
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
  blocks: {},
  block: () => undefined,
})

/** The gates the API refuses an Agentic chat with, which hold until the app restarts. */
export const AGENTIC_GATES = new Set([
  "agent_not_installed",
  "tool_calls_unsupported",
  "window_below_floor",
])

/** What a new chat on the model may be, with a gate the API has since refused it by. */
export function chatModesOf(
  model: ModelSelection | null,
  blocks: NewChatModePicks["blocks"]
): ChatModes | null {
  const modes = model?.capability?.modes
  if (!model || !modes) return null
  const gate = blocks[modelKey(model)]
  return gate && modes.agentic_allowed
    ? { ...modes, agentic_allowed: false, blocked: gate, default_mode: "basic" }
    : modes
}

/**
 * The mode the next new chat starts in: the one picked for this model, else
 * its default. Null for a model that reports no modes.
 */
export function resolveNewChatChoice(
  model: ModelSelection | null,
  picks: NewChatModePicks["picks"],
  blocks: NewChatModePicks["blocks"] = {}
): NewChatChoice | null {
  const modes = chatModesOf(model, blocks)
  if (!model || !modes) return null
  const picked = picks[modelKey(model)]
  const wanted = picked ?? modes.default_mode
  const mode = wanted === "agentic" && !modes.agentic_allowed ? "basic" : wanted
  return { mode, chosen: picked === mode }
}

export function useChatModes(model: ModelSelection | null) {
  const { blocks } = useContext(NewChatModeContext)
  return useMemo(() => chatModesOf(model, blocks), [model, blocks])
}

export function useNewChatChoice(model: ModelSelection | null) {
  const { picks, blocks } = useContext(NewChatModeContext)
  const choice = resolveNewChatChoice(model, picks, blocks)
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

export function useBlockAgentic() {
  return useContext(NewChatModeContext).block
}
