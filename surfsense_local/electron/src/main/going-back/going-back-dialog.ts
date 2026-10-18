import { app, dialog, type MessageBoxOptions } from "electron"

import type { Question } from "./offer-going-back.ts"

// English, like the quit confirmation: main's own text is not translated.
export async function askAboutGoingBack(question: Question): Promise<boolean> {
  // No window yet: without this the dialog can open behind other apps. `steal`
  // and the bounce are macOS only; Windows flashes the dialog's own taskbar button.
  app.focus({ steal: true })
  const bounce = app.dock?.bounce("critical")
  const { response } = await dialog.showMessageBox(dialogFor(question))
  if (bounce !== undefined) app.dock?.cancelBounce(bounce)
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
        ...cannotGoBackText[question.reason],
      }
  }
}

const cannotGoBackText = {
  "nothing-to-go-back-to": {
    message: "This version of SurfSense can't open your data.",
    detail:
      "A newer version updated it, and no copy from before that update was found. " +
      "Install the newer version again to keep using your data.",
  },
  "failed-data-unchanged": {
    message: "SurfSense couldn't go back to this version.",
    detail:
      "Your data is as the newer version left it. Install the newer version again to keep using it.",
  },
  "failed-data-may-have-changed": {
    message: "SurfSense couldn't go back to this version.",
    detail:
      "It stopped partway, so your data may have changed. A full copy from before it " +
      "started is in the backups folder in your SurfSense data folder.",
  },
} satisfies Record<Extract<Question, { kind: "cannot-go-back" }>["reason"], { message: string; detail: string }>

function formatDate(date: Date): string {
  return date.toLocaleString("en", { dateStyle: "long", timeStyle: "short" })
}
