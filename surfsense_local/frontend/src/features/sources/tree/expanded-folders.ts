// Each workspace's open folders as JSON, `{"1": [2, 5]}`.
export const EXPANDED_FOLDERS_KEY = "surfsense:expanded-folders:v1"

function readAll(): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(EXPANDED_FOLDERS_KEY) ?? "{}"
    )
    return typeof value === "object" && value !== null && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {}
  } catch {
    return {}
  }
}

/** The folders a workspace had open in its last session; none when there are none. */
export function readExpandedFolders(workspaceId: number): ReadonlySet<number> {
  const stored = readAll()[String(workspaceId)]
  if (!Array.isArray(stored)) return new Set()
  return new Set(
    stored.filter((id): id is number => Number.isInteger(id) && id > 0)
  )
}

export function rememberExpandedFolders(
  workspaceId: number,
  folderIds: ReadonlySet<number>
) {
  const everyWorkspace = readAll()
  if (folderIds.size > 0) everyWorkspace[String(workspaceId)] = [...folderIds]
  else delete everyWorkspace[String(workspaceId)]
  try {
    localStorage.setItem(EXPANDED_FOLDERS_KEY, JSON.stringify(everyWorkspace))
  } catch {
    // Private browsing and full disks throw; the folders stay open this session.
  }
}
