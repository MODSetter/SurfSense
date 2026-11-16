import { everySource, type ScopeMarks } from "./scope-state"

// Each workspace's ticks as JSON, `{"1": {"all": false, "folders": [[2, true]], "documents": []}}`.
export const SOURCE_TICKS_KEY = "surfsense:source-ticks:v1"

type StoredMarks = {
  all: boolean
  folders: [number, boolean][]
  documents: [number, boolean][]
}

function readAll(): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(SOURCE_TICKS_KEY) ?? "{}"
    )
    return typeof value === "object" && value !== null && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {}
  } catch {
    return {}
  }
}

function marksMap(value: unknown): Map<number, boolean> | null {
  if (!Array.isArray(value)) return null
  const entries = value.filter(
    (entry): entry is [number, boolean] =>
      Array.isArray(entry) &&
      Number.isInteger(entry[0]) &&
      typeof entry[1] === "boolean"
  )
  return new Map(entries)
}

/** A workspace's ticks from its last session; none ticked when there are none. */
export function readRememberedTicks(workspaceId: number): ScopeMarks {
  const stored = readAll()[String(workspaceId)]
  if (typeof stored !== "object" || stored === null) return everySource(false)
  const { all, folders, documents } = stored as Record<string, unknown>
  const folderMarks = marksMap(folders)
  const documentMarks = marksMap(documents)
  if (typeof all !== "boolean" || !folderMarks || !documentMarks) {
    return everySource(false)
  }
  return { all, folders: folderMarks, documents: documentMarks }
}

export function rememberTicks(workspaceId: number, marks: ScopeMarks) {
  const stored: StoredMarks = {
    all: marks.all,
    folders: [...marks.folders],
    documents: [...marks.documents],
  }
  const everyWorkspace = { ...readAll(), [String(workspaceId)]: stored }
  try {
    localStorage.setItem(SOURCE_TICKS_KEY, JSON.stringify(everyWorkspace))
  } catch {
    // Private browsing and full disks throw; the ticks last this session.
  }
}
