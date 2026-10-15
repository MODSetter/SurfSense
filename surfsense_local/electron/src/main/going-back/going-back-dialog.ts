import { dialog, type MessageBoxOptions } from "electron"

import type { Question } from "./offer-going-back.ts"

// English, like the quit confirmation: main's own text is not translated.
export async function askAboutGoingBack(question: Question): Promise<boolean> {
  const { response } = await dialog.showMessageBox(dialogFor(question))
  return question.kind !== "cannot-go-back" && response === 1
}

function dialogFor(question: Question): MessageBoxOptions {
  switch (question.kind) {
    case "undo":
      return {
        type: "question",
        buttons: ["Quit", "Change it back"],
        defaultId: 1,
        cancelId: 0,
        message: "A newer version of SurfSense updated your data.",
        detail:
          "This version can't open it as it is, but it can change it back. " +
          "Your documents and chats stay. A few things only the newer version " +
          "has may be removed. A copy of everything is kept first.",
      }
    case "restore":
      return {
        type: "question",
        buttons: ["Quit", "Use the copy"],
        defaultId: 1,
        cancelId: 0,
        message: question.afterFailedUndo
          ? "SurfSense couldn't change your data back."
          : "A newer version of SurfSense updated your data.",
        detail:
          `This version can use the copy saved on ${formatDate(question.savedAt)}, ` +
          "before the update. Anything you added after that won't be in it. " +
          "Your current data is kept as a copy.",
      }
    case "cannot-go-back":
      return {
        type: "warning",
        buttons: ["Quit"],
        defaultId: 0,
        message:
          question.reason === "going-back-failed"
            ? "SurfSense couldn't go back to this version."
            : "This version of SurfSense can't open your data.",
        detail:
          question.reason === "going-back-failed"
            ? "Your data is as the newer version left it. Install the newer version again to keep using it."
            : "A newer version updated it, and no copy from before that update was found. " +
              "Install the newer version again to keep using your data.",
      }
  }
}

function formatDate(date: Date): string {
  return date.toLocaleString("en", { dateStyle: "long", timeStyle: "short" })
}
