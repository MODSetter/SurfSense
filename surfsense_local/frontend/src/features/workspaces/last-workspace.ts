const LAST_WORKSPACE_KEY = "surfsense:last-workspace:v1"

/** The workspace chosen last, before the list says whether it still exists. */
export function readStoredWorkspaceId(): number | null {
  try {
    const stored = Number(localStorage.getItem(LAST_WORKSPACE_KEY))
    return Number.isInteger(stored) && stored > 0 ? stored : null
  } catch {
    return null
  }
}

export function rememberWorkspace(id: number) {
  try {
    localStorage.setItem(LAST_WORKSPACE_KEY, String(id))
  } catch {
    // Selection still works for this session when storage is unavailable.
  }
}
