import { rm } from "node:fs/promises"
import { dirname, join } from "node:path"

/**
 * On Windows electron-updater patches installer.exe, which every install
 * overwrites with the installed version, but reuses current.blockmap from the
 * last version it downloaded. Once the two differ (a download not yet installed,
 * a version installed by hand) the patched file fails its sha512 and the update
 * downloads in full. Without the file it fetches the installed version's
 * blockmap, about 1 MB, which always matches. On macOS update.zip and
 * current.blockmap come from the same download, so both stay; Linux has neither.
 */
export async function dropStaleBlockmap(
  pendingFolder: string,
  platform: NodeJS.Platform
): Promise<void> {
  if (platform !== "win32") return
  await rm(join(dirname(pendingFolder), "current.blockmap"), { force: true }).catch(
    () => undefined
  )
}
