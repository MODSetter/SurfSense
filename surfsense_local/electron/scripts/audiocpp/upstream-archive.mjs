// macOS: upstream's own archive, which already meets the app's floor there.
import { mkdirSync } from "node:fs"
import { join } from "node:path"

import { download, unpack } from "./download.mjs"
import { MAC_ARCHIVE } from "./pins.mjs"

/** Unpack the pinned archive in `work`; returns where its files and specs are. */
export async function unpackUpstream(work) {
  const archive = join(work, "audiocpp.tar.gz")
  const root = join(work, "upstream")
  mkdirSync(root)
  console.log(`downloading ${MAC_ARCHIVE.url}`)
  await download(MAC_ARCHIVE, archive)
  unpack(archive, root)
  return { binaries: root, source: root }
}
