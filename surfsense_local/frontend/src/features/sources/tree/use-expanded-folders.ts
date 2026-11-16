import { useCallback, useEffect, useState } from "react"

import {
  readExpandedFolders,
  rememberExpandedFolders,
} from "./expanded-folders"
import type { SourceIndex } from "./source-index"

const readFor = (workspaceId: number | null): ReadonlySet<number> =>
  workspaceId === null ? new Set() : readExpandedFolders(workspaceId)

/**
 * The folders open in the sources tree, kept per workspace across launches.
 * With no workspace they last only while the tree is mounted.
 */
export function useExpandedFolders(
  workspaceId: number | null,
  index: SourceIndex
) {
  // The open folders belong to the workspace they were read for, so a switch reloads them.
  const [held, setHeld] = useState(() => ({
    workspaceId,
    expanded: readFor(workspaceId),
  }))
  if (held.workspaceId !== workspaceId) {
    setHeld({ workspaceId, expanded: readFor(workspaceId) })
  } else if (
    // A folder gone from the listing is forgotten, since SQLite can give its
    // id to the next folder made. Before the listing arrives there is no root.
    index.rootFolderId !== null &&
    [...held.expanded].some((id) => !index.folders.has(id))
  ) {
    setHeld({
      ...held,
      expanded: new Set(
        [...held.expanded].filter((id) => index.folders.has(id))
      ),
    })
  }

  useEffect(() => {
    if (held.workspaceId !== null) {
      rememberExpandedFolders(held.workspaceId, held.expanded)
    }
  }, [held])

  const setFolderExpanded = useCallback(
    (folderId: number, open: boolean) =>
      setHeld((current) => {
        if (current.expanded.has(folderId) === open) return current
        const expanded = new Set(current.expanded)
        if (open) expanded.add(folderId)
        else expanded.delete(folderId)
        return { ...current, expanded }
      }),
    []
  )

  return { expanded: held.expanded, setFolderExpanded }
}
