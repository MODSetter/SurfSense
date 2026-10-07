import { dialog, type BrowserWindow } from "electron"

import type { QuitConfirmation } from "./confirm-running-replies.ts"

// The API answers stop-all within its own bound; this one only guards a hang.
const SAVE_TIMEOUT_MS = 5_000

/** The quit confirmation against this run's API, asked in a native dialog. */
export function apiQuitConfirmation(
  apiUrl: string,
  parent: () => BrowserWindow | null
): QuitConfirmation {
  return {
    countRunning: async () => {
      const reply = await fetch(`${apiUrl}/chat/runs`, {
        signal: AbortSignal.timeout(2_000),
      })
      const { active } = (await reply.json()) as { active?: unknown }
      return typeof active === "number" ? active : 0
    },
    ask: async (count) => {
      // English, like the application menu: main's own text is not translated.
      const options = {
        type: "question" as const,
        buttons: ["Cancel", "Quit"],
        defaultId: 1,
        cancelId: 0,
        message:
          count === 1
            ? "1 reply is still being written."
            : `${count} replies are still being written.`,
        detail: "Quitting saves what they have so far.",
      }
      const owner = parent()
      const { response } = owner
        ? await dialog.showMessageBox(owner, options)
        : await dialog.showMessageBox(options)
      return response === 1
    },
    saveRunning: async () => {
      await fetch(`${apiUrl}/chat/runs/stop-all`, {
        method: "POST",
        signal: AbortSignal.timeout(SAVE_TIMEOUT_MS),
      })
    },
  }
}
