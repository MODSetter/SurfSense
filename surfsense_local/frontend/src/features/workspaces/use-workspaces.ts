import { useMemo, useState } from "react"

import {
  createWorkspace,
  deleteWorkspace,
  renameWorkspace,
  type Workspace,
} from "./api"

const LAST_WORKSPACE_KEY = "surfsense-local:last-workspace:v1"

function readLastWorkspaceId(workspaces: Workspace[]): number | null {
  try {
    const stored = Number(localStorage.getItem(LAST_WORKSPACE_KEY))
    if (workspaces.some((workspace) => workspace.id === stored)) {
      return stored
    }
  } catch {
    // Storage can be disabled; the first workspace is a safe fallback.
  }
  // Null when the list is empty, so nothing is active.
  return workspaces[0]?.id ?? null
}

function rememberWorkspace(id: number) {
  try {
    localStorage.setItem(LAST_WORKSPACE_KEY, String(id))
  } catch {
    // Selection still works for this session when storage is unavailable.
  }
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

export function useWorkspaces(initialWorkspaces: Workspace[]) {
  const [workspaces, setWorkspaces] = useState(initialWorkspaces)
  const [activeId, setActiveId] = useState(() =>
    readLastWorkspaceId(initialWorkspaces)
  )
  const [error, setError] = useState<string | null>(null)
  const [isMutating, setIsMutating] = useState(false)

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeId),
    [activeId, workspaces]
  )

  const select = (id: number) => {
    if (
      id === activeId ||
      !workspaces.some((workspace) => workspace.id === id)
    ) {
      return
    }
    rememberWorkspace(id)
    setActiveId(id)
  }

  const create = async (name: string) => {
    setIsMutating(true)
    setError(null)
    try {
      const workspace = await createWorkspace(name)
      setWorkspaces((current) => [...current, workspace])
      rememberWorkspace(workspace.id)
      setActiveId(workspace.id)
      return true
    } catch (cause) {
      setError(messageFrom(cause))
      return false
    } finally {
      setIsMutating(false)
    }
  }

  const rename = async (id: number, name: string) => {
    setIsMutating(true)
    setError(null)
    try {
      const workspace = await renameWorkspace(id, name)
      setWorkspaces((current) =>
        current.map((candidate) =>
          candidate.id === workspace.id ? workspace : candidate
        )
      )
      return true
    } catch (cause) {
      setError(messageFrom(cause))
      return false
    } finally {
      setIsMutating(false)
    }
  }

  const remove = async (id: number) => {
    setIsMutating(true)
    setError(null)
    try {
      await deleteWorkspace(id)
      const remaining = workspaces.filter((workspace) => workspace.id !== id)
      setWorkspaces(remaining)

      // Deleting the last one leaves nothing active; the empty state takes over.
      if (id === activeId) {
        const nextId = remaining[0]?.id ?? null
        if (nextId !== null) rememberWorkspace(nextId)
        setActiveId(nextId)
      }
      return true
    } catch (cause) {
      setError(messageFrom(cause))
      return false
    } finally {
      setIsMutating(false)
    }
  }

  return {
    workspaces,
    activeWorkspace,
    error,
    isMutating,
    select,
    create,
    rename,
    remove,
    clearError: () => setError(null),
  }
}
