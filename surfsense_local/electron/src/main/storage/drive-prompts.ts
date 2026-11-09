import { dialog } from "electron"

import type { DrivePrompts } from "./settle-before-boot.ts"

// English, like the application menu: main's own text is not translated.
export const drivePrompts: DrivePrompts = {
  dataMissing: async (path) => {
    const { response } = await dialog.showMessageBox({
      type: "warning",
      buttons: ["Try again", "Choose folder…", "Quit"],
      defaultId: 0,
      cancelId: 2,
      message: "SurfSense can’t find your data",
      detail: `Your data folder isn’t available:\n${path}\n\nConnect the drive it’s on and try again, or choose where the folder is now. SurfSense can’t start without it.`,
    })
    return (["retry", "choose", "quit"] as const)[response] ?? "quit"
  },
  modelsMissing: async (path) => {
    const { response } = await dialog.showMessageBox({
      type: "warning",
      buttons: ["Try again", "Continue without local models", "Quit"],
      defaultId: 0,
      cancelId: 2,
      message: "SurfSense can’t find your models",
      detail: `Your models folder isn’t available:\n${path}\n\nConnect the drive it’s on and try again. You can also continue: models on a server keep working, but local models can’t be used or downloaded until the folder is back.`,
    })
    return (["retry", "continue", "quit"] as const)[response] ?? "quit"
  },
  pickDataFolder: async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog({
      title: "Choose your SurfSense data folder",
      properties: ["openDirectory"],
    })
    return canceled ? null : (filePaths[0] ?? null)
  },
  notADataFolder: async (path) => {
    await dialog.showMessageBox({
      type: "warning",
      message: "That folder doesn’t hold SurfSense data",
      detail: `SurfSense found no data in:\n${path}`,
    })
  },
}
