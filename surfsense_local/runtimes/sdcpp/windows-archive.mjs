// Windows: upstream's Vulkan archive, which meets the app's floor there once
// the MSVC runtime it was built against ships beside it.
import { mkdirSync } from "node:fs"
import { join } from "node:path"

import { download, unpack } from "../pinned-download.mjs"
import { WINDOWS_ARCHIVE } from "./pins.mjs"

/** Unpack the pinned archive in `work`; returns the folder holding the server. */
export async function unpackWindowsArchive(work) {
  const archive = join(work, "sdcpp.zip")
  const root = join(work, "upstream")
  mkdirSync(root)
  console.log(`downloading ${WINDOWS_ARCHIVE.url}`)
  await download(WINDOWS_ARCHIVE, archive)
  unpack(archive, root)
  return root
}
