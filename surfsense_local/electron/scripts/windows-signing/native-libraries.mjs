// The libraries a Windows app loads code from: electron-builder signs only .exe
// files, so these are the ones left to sign.
import { closeSync, openSync, readSync, readdirSync } from "node:fs"
import { join } from "node:path"

const LIBRARY = /\.(dll|pyd|node)$/i

/** Every native library under `root`, sorted. */
export function nativeLibraries(root) {
  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && LIBRARY.test(entry.name))
    .map((entry) => join(entry.parentPath, entry.name))
    .filter(isPeImage)
    .sort()
}

// Every PE image starts "MZ". A data file named like a library would fail
// signtool, and with it the whole batch.
function isPeImage(path) {
  const head = Buffer.alloc(2)
  const fd = openSync(path, "r")
  try {
    return readSync(fd, head, 0, 2, 0) === 2 && head.toString("latin1") === "MZ"
  } finally {
    closeSync(fd)
  }
}
