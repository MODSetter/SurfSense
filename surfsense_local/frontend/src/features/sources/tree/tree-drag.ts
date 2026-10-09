import type { FolderKey } from "./source-index"

export type DraggedSource = { kind: "folder" | "document"; id: number }

type DragData = Record<string | symbol, unknown>

// A row being dragged, so a drag from anywhere else is never moved.
export const sourceDragData = (source: DraggedSource) => ({
  type: "source",
  ...source,
})

export function draggedSourceOf(data: DragData): DraggedSource | null {
  const { type, kind, id } = data
  return type === "source" &&
    (kind === "folder" || kind === "document") &&
    typeof id === "number"
    ? { kind, id }
    : null
}

// Where a drop files into: a folder row into itself, a source row into the
// folder holding it, the panel into the top level.
export const dropTargetData = (into: FolderKey) => ({ type: "into", into })

export function dropFolderOf(
  data: DragData | undefined
): FolderKey | undefined {
  return data?.type === "into" ? (data.into as FolderKey) : undefined
}
