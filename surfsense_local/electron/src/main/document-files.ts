import { readdir } from "node:fs/promises"
import { isAbsolute, join, relative, resolve } from "node:path"

// Mirrors original_path() in the backend's modules/documents/original_file.py.
// Each document folder holds one upload under its own name; legacy folders hold
// original.<ext> beside an unread extracted.md, which is never the original.
// Do not copy the backend's format allowlist: a newly supported upload should
// open immediately.
const LEGACY_EXTRACTED = "extracted.md"
// Finder writes .DS_Store into any folder it shows; Explorer writes the others.
const OS_LITTER = new Set(["thumbs.db", "desktop.ini"])

function isOriginal(name: string): boolean {
  const folded = name.toLowerCase()
  return (
    !name.startsWith(".") &&
    !OS_LITTER.has(folded) &&
    folded !== LEGACY_EXTRACTED
  )
}

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
    (entry) => entry.isFile() && isOriginal(entry.name)
  )
  if (originals.length !== 1) {
    throw new Error("The imported file is no longer available.")
  }

  return join(directory, originals[0].name)
}
