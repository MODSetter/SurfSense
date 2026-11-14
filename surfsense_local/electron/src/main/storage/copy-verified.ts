import { createHash } from "node:crypto"
import { createReadStream, createWriteStream } from "node:fs"
import { link, mkdir, open, symlink, utimes } from "node:fs/promises"
import { dirname, isAbsolute, join, relative } from "node:path"
import { Transform } from "node:stream"
import { pipeline } from "node:stream/promises"

import type { Scan, ScannedItem } from "./scan-entries.ts"

// A write-back cache could lose these if the drive is pulled right after the switch.
const SYNC_FROM_BYTES = 1 << 20
const HIGH_WATER_MARK = 1 << 20

async function hashFile(path: string, signal: AbortSignal, onBytes: (n: number) => void): Promise<string> {
  const hash = createHash("sha256")
  for await (const chunk of createReadStream(path, { highWaterMark: HIGH_WATER_MARK, signal })) {
    hash.update(chunk as Buffer)
    onBytes((chunk as Buffer).length)
  }
  return hash.digest("hex")
}

async function copyFile(
  from: string,
  to: string,
  item: Extract<ScannedItem, { kind: "file" }>,
  signal: AbortSignal,
  onBytes: (n: number) => void,
): Promise<string> {
  const hash = createHash("sha256")
  const counted = new Transform({
    transform(chunk: Buffer, _encoding, done) {
      hash.update(chunk)
      onBytes(chunk.length)
      done(null, chunk)
    },
  })
  await pipeline(
    createReadStream(from, { highWaterMark: HIGH_WATER_MARK }),
    counted,
    createWriteStream(to, { mode: item.mode }),
    { signal },
  )
  if (item.size >= SYNC_FROM_BYTES || item.path.includes(".db")) {
    const handle = await open(to, "r+")
    await handle.sync()
    await handle.close()
  }
  // A scan keeps a cache by mtime, and a resumed download compares it.
  await utimes(to, item.atime, item.mtime)
  return hash.digest("hex")
}

// An absolute link that pointed inside the old root must point inside the new one.
function repointedLink(target: string, fromRoot: string, toRoot: string): string {
  if (!isAbsolute(target)) return target
  const inside = relative(fromRoot, target)
  if (inside.startsWith("..") || isAbsolute(inside)) return target
  return join(toRoot, inside)
}

/** Copy, then read every copied file back and compare, before the originals can ever go. */
export async function copyVerified(options: {
  scan: Scan
  fromRoot: string
  /** Where the bytes go now. */
  stagingRoot: string
  /** Where they end up, for links that name it. */
  finalRoot: string
  signal: AbortSignal
  onBytes: (phase: "copying" | "verifying", bytes: number) => void
}): Promise<void> {
  const { scan, fromRoot, stagingRoot, finalRoot, signal, onBytes } = options
  const hashes = new Map<string, string>()

  for (const item of scan.items) {
    signal.throwIfAborted()
    const target = join(stagingRoot, item.path)
    await mkdir(dirname(target), { recursive: true })
    if (item.kind === "directory") {
      await mkdir(target, { recursive: true })
    } else if (item.kind === "file") {
      const digest = await copyFile(join(fromRoot, item.path), target, item, signal, (n) =>
        onBytes("copying", n),
      )
      hashes.set(item.path, digest)
    } else if (item.kind === "hardlink") {
      await link(join(stagingRoot, item.to), target)
    } else {
      // A junction needs no privilege on Windows, where a directory symlink does.
      await symlink(
        repointedLink(item.target, fromRoot, finalRoot),
        target,
        item.toDirectory ? "junction" : "file",
      )
    }
  }

  for (const [path, expected] of hashes) {
    signal.throwIfAborted()
    const actual = await hashFile(join(stagingRoot, path), signal, (n) => onBytes("verifying", n))
    if (actual !== expected) throw new CopyMismatchError(path)
  }
}

export class CopyMismatchError extends Error {
  constructor(path: string) {
    super(`the copy of ${path} does not match the original`)
  }
}
