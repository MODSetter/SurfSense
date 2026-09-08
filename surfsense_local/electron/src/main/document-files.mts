import { readdir } from "node:fs/promises"
import { isAbsolute, join, relative, resolve } from "node:path"

// The backend validates uploads before creating original.<suffix>. Do not copy
// its format allowlist here: a newly supported upload should open immediately.
const ORIGINAL_FILENAME = /^original\.[A-Za-z0-9]{1,16}$/

function positiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) > 0
}

export async function managedOriginalPath(
  dataDir: string,
  workspaceId: unknown,
  documentId: unknown
): Promise<string> {
  if (!positiveInteger(workspaceId) || !positiveInteger(documentId)) {
    throw new Error("Invalid source identifier.")
  }

  const documentsRoot = resolve(dataDir, "data", "workspaces")
  const directory = resolve(
    documentsRoot,
    String(workspaceId),
    "documents",
    String(documentId)
  )
  const relativeDirectory = relative(documentsRoot, directory)
  if (relativeDirectory.startsWith("..") || isAbsolute(relativeDirectory)) {
    throw new Error("Invalid source location.")
  }

  const entries = await readdir(directory, { withFileTypes: true })
  const originals = entries.filter(
    (entry) => entry.isFile() && ORIGINAL_FILENAME.test(entry.name)
  )
  if (originals.length !== 1) {
    throw new Error("The imported file is no longer available.")
  }

  return join(directory, originals[0].name)
}
