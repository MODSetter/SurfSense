import { getFiles } from "@atlaskit/pragmatic-drag-and-drop/external/file"

import type { UploadEntry } from "./upload-plan"

type ContainsSource = Parameters<typeof getFiles>[0]["source"]

// Chromium hands a directory's entries out in pages; an empty page ends it.
function readAll(directory: FileSystemDirectoryEntry) {
  const reader = directory.createReader()
  return new Promise<FileSystemEntry[]>((resolve, reject) => {
    const entries: FileSystemEntry[] = []
    const next = () =>
      reader.readEntries((page) => {
        if (page.length === 0) resolve(entries)
        else {
          entries.push(...page)
          next()
        }
      }, reject)
    next()
  })
}

function fileOf(entry: FileSystemFileEntry) {
  return new Promise<File>((resolve, reject) => entry.file(resolve, reject))
}

async function walk(entry: FileSystemEntry, into: UploadEntry[]) {
  if (entry.isFile) {
    into.push({
      file: await fileOf(entry as FileSystemFileEntry),
      relativePath: entry.fullPath.replace(/^\/+/, ""),
    })
  } else if (entry.isDirectory) {
    for (const child of await readAll(entry as FileSystemDirectoryEntry)) {
      await walk(child, into)
    }
  }
}

/**
 * The files of a drop, a dropped folder's at every depth with their paths
 * under it. Entries are taken before any await: the drop's items empty once
 * its event returns.
 */
export async function filesOfDrop(
  source: ContainsSource
): Promise<UploadEntry[]> {
  const entries = source.items.flatMap((item) => {
    const entry =
      item.kind === "file" ? (item.webkitGetAsEntry?.() ?? null) : null
    return entry ? [entry] : []
  })
  if (!entries.some((entry) => entry.isDirectory)) {
    return getFiles({ source }).map((file) => ({ file, relativePath: null }))
  }
  const collected: UploadEntry[] = []
  for (const entry of entries) await walk(entry, collected)
  return collected
}
