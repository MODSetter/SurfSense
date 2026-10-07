import { useCallback, useMemo, useState, type ReactNode } from "react"

import type { ChatMode } from "@/features/models/capability/api"
import { modelKey, type SelectionTarget } from "@/features/models/selection/api"

import { NewChatModeContext } from "./new-chat-mode"

/**
 * Holds the mode picked for each model's next new chat, above the workspace
 * that is open, so a pick holds when the workspace changes.
 */
export function NewChatModeProvider({ children }: { children: ReactNode }) {
  const [picks, setPicks] = useState<Readonly<Record<string, ChatMode>>>({})
  const pick = useCallback((model: SelectionTarget, mode: ChatMode) => {
    const key = modelKey(model)
    setPicks((current) =>
      current[key] === mode ? current : { ...current, [key]: mode }
    )
  }, [])
  const value = useMemo(() => ({ picks, pick }), [picks, pick])
  return (
    <NewChatModeContext.Provider value={value}>
      {children}
    </NewChatModeContext.Provider>
  )
}
