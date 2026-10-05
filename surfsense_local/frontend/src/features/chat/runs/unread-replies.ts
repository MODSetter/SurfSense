// Per workspace and per machine: one person on one machine, and a cleared
// store only loses the dots.
function key(workspaceId: number) {
  return `surfsense:unread-replies:${workspaceId}:v1`
}

/** Threads whose reply ended while another thread was open. */
export function readUnread(workspaceId: number): number[] {
  try {
    const stored = JSON.parse(localStorage.getItem(key(workspaceId)) ?? "[]")
    return Array.isArray(stored)
      ? stored.filter((id): id is number => Number.isInteger(id))
      : []
  } catch {
    return []
  }
}

function write(workspaceId: number, ids: number[]) {
  try {
    localStorage.setItem(key(workspaceId), JSON.stringify(ids))
  } catch {
    // Kept for this session only when storage is unavailable.
  }
}

export function markUnread(workspaceId: number, threadId: number): number[] {
  const current = readUnread(workspaceId)
  if (current.includes(threadId)) return current
  const next = [...current, threadId]
  write(workspaceId, next)
  return next
}

export function markRead(workspaceId: number, threadId: number): number[] {
  const next = readUnread(workspaceId).filter((id) => id !== threadId)
  write(workspaceId, next)
  return next
}
