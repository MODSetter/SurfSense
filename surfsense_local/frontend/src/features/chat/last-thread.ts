function lastThreadKey(workspaceId: number) {
  return `surfsense:last-thread:${workspaceId}:v1`
}

const NEW_CHAT = "new"

/** The thread open last in a workspace; null for a new chat. */
export function readLastThread(workspaceId: number): number | null {
  try {
    const id = Number(localStorage.getItem(lastThreadKey(workspaceId)))
    if (Number.isInteger(id) && id > 0) return id
  } catch {
    // Private browsing: treat as a new chat.
  }
  return null
}

export function rememberThread(workspaceId: number, threadId: number | null) {
  try {
    localStorage.setItem(
      lastThreadKey(workspaceId),
      threadId === null ? NEW_CHAT : String(threadId)
    )
  } catch {
    // Selection remains valid for this session when storage is unavailable.
  }
}
