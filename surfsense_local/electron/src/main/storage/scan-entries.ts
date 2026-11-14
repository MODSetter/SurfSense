import { lstat, readdir, readlink, stat as stat_ } from "node:fs/promises"
import { join } from "node:path"

export type ScannedItem =
  | { kind: "directory"; path: string }
  | { kind: "symlink"; path: string; target: string; toDirectory: boolean }
  | { kind: "file"; path: string; size: number; mode: number; atime: Date; mtime: Date }
  // A later name for a file already listed: the agent's text cache hard-links into threads.
  | { kind: "hardlink"; path: string; to: string }

export type Scan = { items: ScannedItem[]; totalBytes: number }

/** Every item under the named entries of `root`, parents first, relative to `root`. */
export async function scanEntries(root: string, entries: string[]): Promise<Scan> {
  const items: ScannedItem[] = []
  const firstNames = new Map<string, string>()
  let totalBytes = 0

  const visit = async (path: string): Promise<void> => {
    const full = join(root, path)
    const stat = await lstat(full, { bigint: true })
    if (stat.isSymbolicLink()) {
      const target = await readlink(full)
      const toDirectory = await stat_(full).then((s) => s.isDirectory()).catch(() => false)
      items.push({ kind: "symlink", path, target, toDirectory })
    } else if (stat.isDirectory()) {
      items.push({ kind: "directory", path })
      for (const name of await readdir(full)) await visit(join(path, name))
    } else if (stat.isFile()) {
      const identity = `${stat.dev}:${stat.ino}`
      const first = stat.nlink > 1n ? firstNames.get(identity) : undefined
      if (first !== undefined) {
        items.push({ kind: "hardlink", path, to: first })
        return
      }
      if (stat.nlink > 1n) firstNames.set(identity, path)
      const size = Number(stat.size)
      totalBytes += size
      items.push({
        kind: "file",
        path,
        size,
        mode: Number(stat.mode) & 0o777,
        atime: stat.atime,
        mtime: stat.mtime,
      })
    }
    // Sockets and pipes belong to a process that has stopped; they do not move.
  }

  for (const entry of entries) await visit(entry)
  return { items, totalBytes }
}
