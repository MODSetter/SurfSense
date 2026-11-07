import { readLastThread } from "@/features/chat/last-thread"
import { readNextNewChatMode } from "@/features/chat/modes/next-new-chat-mode-store"
import {
  readRightPanelOpen,
  readSidebarOpen,
} from "@/features/dashboard/chrome-prefs"
import { readStoredWorkspaceId } from "@/features/workspaces/last-workspace"

export type StartupLayout = {
  composer: "center" | "bottom"
  sidebarOpen: boolean
  rightPanelOpen: boolean
  // Whether `@` in a new chat's box names sources: only in Agentic chats.
  mentions: boolean
}

/**
 * How the dashboard's first frame will look, from what it stored when last
 * open, read with the readers it uses so the loading frame agrees. A stored
 * source preview is left out: it opens only once the sources have loaded.
 */
export function readStartupLayout(): StartupLayout {
  const workspaceId = readStoredWorkspaceId()
  return {
    composer:
      workspaceId !== null && readLastThread(workspaceId) !== null
        ? "bottom"
        : "center",
    sidebarOpen: readSidebarOpen(),
    rightPanelOpen: readRightPanelOpen(),
    mentions: readNextNewChatMode() === "agentic",
  }
}
