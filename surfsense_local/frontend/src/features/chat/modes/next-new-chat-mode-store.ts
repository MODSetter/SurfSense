import type { ChatMode } from "@/features/models/capability/api"

// Read by the startup frame, so this file imports nothing at run time.
const NEXT_NEW_CHAT_MODE_KEY = "surfsense:next-new-chat-mode:v1"

/** The mode a new chat opens in at the next launch, as last worked out. */
export function readNextNewChatMode(): ChatMode | null {
  try {
    const stored = localStorage.getItem(NEXT_NEW_CHAT_MODE_KEY)
    return stored === "agentic" || stored === "basic" ? stored : null
  } catch {
    return null
  }
}

export function writeNextNewChatMode(mode: ChatMode): void {
  try {
    localStorage.setItem(NEXT_NEW_CHAT_MODE_KEY, mode)
  } catch {
    // The frame then offers no mentions; the composer still does.
  }
}
