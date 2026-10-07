import { useCallback, useMemo, useState, type ReactNode } from "react"

import type { ChatMode } from "@/features/models/capability/api"
import { modelKey, type SelectionTarget } from "@/features/models/selection/api"

import { NewChatModeContext } from "./new-chat-mode"

/**
 * Holds the mode picked for each model's next new chat, and the gates the API
 * refused Agentic by, above the workspace that is open, so both hold when the
 * workspace changes.
 */
export function NewChatModeProvider({ children }: { children: ReactNode }) {
  const [picks, setPicks] = useState<Readonly<Record<string, ChatMode>>>({})
  const [blocks, setBlocks] = useState<Readonly<Record<string, string>>>({})
  const pick = useCallback((model: SelectionTarget, mode: ChatMode) => {
    const key = modelKey(model)
    setPicks((current) =>
      current[key] === mode ? current : { ...current, [key]: mode }
    )
  }, [])
  const block = useCallback((model: SelectionTarget, gate: string) => {
    const key = modelKey(model)
    setBlocks((current) =>
      current[key] === gate ? current : { ...current, [key]: gate }
    )
  }, [])
  const value = useMemo(
    () => ({ picks, pick, blocks, block }),
    [picks, pick, blocks, block]
  )
  return (
    <NewChatModeContext.Provider value={value}>
      {children}
    </NewChatModeContext.Provider>
  )
}
