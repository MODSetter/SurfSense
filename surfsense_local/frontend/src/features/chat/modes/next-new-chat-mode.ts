import type { ModelSelection } from "@/features/models/selection/api"

import { resolveNewChatChoice } from "./new-chat-mode"
import { writeNextNewChatMode } from "./next-new-chat-mode-store"

/**
 * Remembers the mode a new chat on this model opens in after a restart: its
 * default, which a saved pick becomes. The startup frame reads it to offer
 * plugin mentions before the model has loaded.
 */
export function rememberNextNewChatMode(model: ModelSelection | null): void {
  writeNextNewChatMode(resolveNewChatChoice(model, {})?.mode ?? "basic")
}
