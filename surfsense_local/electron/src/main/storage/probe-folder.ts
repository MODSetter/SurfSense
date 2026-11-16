import { link, mkdir, open, rm, rmdir, statfs, writeFile } from "node:fs/promises"
import { join } from "node:path"

import type { StorageKind } from "./marker.ts"

export type ProbeRefusal = "not_writable" | "no_large_files" | "no_hard_links" | "network_drive"

const FOUR_GIB = 4 * 1024 ** 3
// Below this a failed test of a 4 GiB file could be only a full drive.
const ROOM_TO_TEST_LARGE_FILES = 5 * 1024 ** 3

// statfs(2) f_type on Linux: nfs, cifs, smb, smb2. SQLite's locks do not hold there.
const LINUX_NETWORK_FILESYSTEMS = new Set([0x6969, 0xff534d42, 0x517b, 0xfe534d42])

const PROBE = ".surfsense-write-test"

/** Try for real what SurfSense will need here; a filesystem's name says less than this does. */
export async function probeFolder(
  root: string,
  kind: StorageKind,
  platform: NodeJS.Platform = process.platform,
): Promise<{ freeBytes: number } | { refused: ProbeRefusal }> {
  const created = await mkdir(root, { recursive: true }).catch(() => null)
  const probe = join(root, PROBE)
  const linked = `${probe}.link`
  try {
    await writeFile(probe, "surfsense")
  } catch {
    return { refused: "not_writable" }
  }
  try {
    const stats = await statfs(root)
    const freeBytes = stats.bavail * stats.bsize
    if (kind === "data" && platform === "linux" && LINUX_NETWORK_FILESYSTEMS.has(stats.type)) {
      return { refused: "network_drive" }
    }
    if (kind === "data") {
      // The agent's text cache links each file into its threads; exFAT cannot.
      const hardLinks = await link(probe, linked).then(() => true, () => false)
      if (!hardLinks) return { refused: "no_hard_links" }
    }
    if (freeBytes >= ROOM_TO_TEST_LARGE_FILES) {
      // FAT32 stops at 4 GiB; models are often past it. A sparse extension writes nothing.
      const handle = await open(probe, "r+")
      const large = await handle.truncate(FOUR_GIB + 1).then(() => true, () => false)
      await handle.close()
      if (!large) return { refused: "no_large_files" }
    }
    return { freeBytes }
  } finally {
    await rm(linked, { force: true }).catch(() => undefined)
    await rm(probe, { force: true }).catch(() => undefined)
    // Only a folder this check made: an empty one is left by a move that never happens.
    if (created) await rmdir(root).catch(() => undefined)
  }
}
