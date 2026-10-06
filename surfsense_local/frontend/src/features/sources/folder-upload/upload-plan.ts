import { isSupportedSourceFile } from "../api"

/** One file to send, with its path under the folder it was picked or dropped in. */
export type UploadEntry = { file: File; relativePath: string | null }

export type UploadBatch = {
  files: File[]
  // Index for index with `files`; null when nothing came from a folder.
  relativePaths: string[] | null
}

export type UploadPlan = {
  batches: UploadBatch[]
  unsupported: File[]
  tooLarge: File[]
  // Folder clutter (.git and the like), skipped without a word per file.
  ignored: number
}

// The server refuses a file over this with 413, failing its whole request.
export const MAX_SOURCE_BYTES = 500 * 1024 * 1024
// Per request; an estimate that keeps one request short and one failure small.
export const MAX_BATCH_FILES = 50
export const MAX_BATCH_BYTES = 200 * 1024 * 1024

// Hosted SurfSense's default excludes for a folder.
const IGNORED_NAMES = new Set([
  ".git",
  "node_modules",
  "__pycache__",
  ".ds_store",
  ".obsidian",
  ".trash",
])

function isIgnored(relativePath: string | null) {
  return (
    relativePath !== null &&
    relativePath
      .split("/")
      .some((segment) => IGNORED_NAMES.has(segment.toLowerCase()))
  )
}

/** Splits files into requests the server takes, setting aside what it would refuse. */
export function planUpload(entries: UploadEntry[]): UploadPlan {
  const plan: UploadPlan = {
    batches: [],
    unsupported: [],
    tooLarge: [],
    ignored: 0,
  }
  const fromFolder = entries.some((entry) => entry.relativePath !== null)
  let batch: UploadBatch | null = null
  let batchBytes = 0
  for (const { file, relativePath } of entries) {
    if (isIgnored(relativePath)) {
      plan.ignored += 1
      continue
    }
    if (!isSupportedSourceFile(file)) {
      plan.unsupported.push(file)
      continue
    }
    if (file.size > MAX_SOURCE_BYTES) {
      plan.tooLarge.push(file)
      continue
    }
    if (
      batch === null ||
      batch.files.length >= MAX_BATCH_FILES ||
      (batch.files.length > 0 && batchBytes + file.size > MAX_BATCH_BYTES)
    ) {
      batch = { files: [], relativePaths: fromFolder ? [] : null }
      batchBytes = 0
      plan.batches.push(batch)
    }
    batch.files.push(file)
    batch.relativePaths?.push(relativePath ?? file.name)
    batchBytes += file.size
  }
  return plan
}
