import { useEffect, useEffectEvent } from "react"

import {
  subscribeToWorkspaceChanges,
  type WorkspaceChangeKind,
} from "./workspace-changes"

/** Calls `onChange` when the workspace reports a change of this kind. */
export function useWorkspaceChanges(
  workspaceId: number,
  kind: WorkspaceChangeKind,
  onChange: () => void
) {
  const changed = useEffectEvent(onChange)

  useEffect(
    () => subscribeToWorkspaceChanges(workspaceId, kind, () => changed()),
    [workspaceId, kind]
  )
}
