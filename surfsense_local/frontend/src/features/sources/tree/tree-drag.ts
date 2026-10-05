import type { DragEvent } from "react"

// A row dragged inside the tree; files from the desktop carry "Files" instead.
const SOURCE_DRAG_TYPE = "application/x-surfsense-source"

export type DraggedSource = { kind: "folder" | "document"; id: number }

export function startSourceDrag(event: DragEvent, source: DraggedSource) {
  event.dataTransfer.setData(SOURCE_DRAG_TYPE, JSON.stringify(source))
  event.dataTransfer.effectAllowed = "move"
}

export function carriesSource(event: DragEvent) {
  return Array.from(event.dataTransfer.types).includes(SOURCE_DRAG_TYPE)
}

export function draggedSource(event: DragEvent): DraggedSource | null {
  try {
    const parsed: unknown = JSON.parse(
      event.dataTransfer.getData(SOURCE_DRAG_TYPE)
    )
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "kind" in parsed &&
      "id" in parsed &&
      (parsed.kind === "folder" || parsed.kind === "document") &&
      typeof parsed.id === "number"
    ) {
      return { kind: parsed.kind, id: parsed.id }
    }
  } catch {
    // Not one of ours.
  }
  return null
}
