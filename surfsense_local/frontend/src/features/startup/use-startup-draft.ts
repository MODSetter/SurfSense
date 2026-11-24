import { useState } from "react"

import type { StartupDraft } from "./startup-input"
import { useStartupInput } from "./startup-input-context"

/**
 * What was typed into the startup frame's box, if anything, read once when
 * the composer mounts: a draft that arrives later belongs to no composer on
 * screen. The composer leaves its own mount focus off when there is one, as
 * that focus moves the caret to the end.
 */
export function useStartupDraft(): StartupDraft | null {
  const startup = useStartupInput()
  const [draft] = useState(() => startup?.peek() ?? null)
  return draft
}
