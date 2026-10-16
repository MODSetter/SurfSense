import { useEffect, useEffectEvent } from "react"

import {
  subscribeToWorkspaceChanges,
  type WorkspaceChange,
  type WorkspaceChangeKind,
} from "./workspace-changes"

/**
 * Calls `onChange` when the workspace reports a change of this kind, with the
 * change; without one when a dropped stream came back.
 */
export function useWorkspaceChanges(
  workspaceId: number,
  kind: WorkspaceChangeKind,
  onChange: (change?: WorkspaceChange) => void
) {
  const changed = useEffectEvent(onChange)

  useEffect(
    () =>
      subscribeToWorkspaceChanges(workspaceId, kind, (change) =>
        changed(change)
      ),
    [workspaceId, kind]
  )
}
