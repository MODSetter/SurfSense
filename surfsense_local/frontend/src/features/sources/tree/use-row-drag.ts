import { createElement, useEffect, useRef, type RefObject } from "react"
import { flushSync } from "react-dom"
import { createRoot } from "react-dom/client"
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine"
import {
  draggable,
  dropTargetForElements,
} from "@atlaskit/pragmatic-drag-and-drop/element/adapter"
import { pointerOutsideOfPreview } from "@atlaskit/pragmatic-drag-and-drop/element/pointer-outside-of-preview"
import { setCustomNativeDragPreview } from "@atlaskit/pragmatic-drag-and-drop/element/set-custom-native-drag-preview"
import { dropTargetForExternal } from "@atlaskit/pragmatic-drag-and-drop/external/adapter"
import { containsFiles } from "@atlaskit/pragmatic-drag-and-drop/external/file"

import { DragChip } from "./drag-chip"
import type { FolderKey } from "./source-index"
import {
  draggedSourceOf,
  dropTargetData,
  sourceDragData,
  type DraggedSource,
} from "./tree-drag"

/** Where a row files what is dropped on it, and what it takes. */
export type RowDrag = {
  into: FolderKey
  // Absent folders to move into, the row neither drags nor takes rows.
  movable: boolean
  // False while an upload runs, as the panel refuses files then.
  takesFiles: boolean
}

type Latest = RefObject<{
  source: DraggedSource
  name: string
  into: FolderKey
}>

function takeFiles(element: HTMLElement, latest: Latest) {
  return dropTargetForExternal({
    element,
    canDrop: containsFiles,
    getData: () => dropTargetData(latest.current.into),
  })
}

function moveRows(element: HTMLElement, latest: Latest) {
  return combine(
    draggable({
      element,
      getInitialData: () => sourceDragData(latest.current.source),
      onGenerateDragPreview: ({ nativeSetDragImage }) =>
        setCustomNativeDragPreview({
          nativeSetDragImage,
          getOffset: pointerOutsideOfPreview({ x: "12px", y: "8px" }),
          render: ({ container }) => {
            const root = createRoot(container)
            const { source, name } = latest.current
            // The browser takes its picture as the drag starts.
            flushSync(() =>
              root.render(createElement(DragChip, { kind: source.kind, name }))
            )
            return () => root.unmount()
          },
        }),
    }),
    dropTargetForElements({
      element,
      canDrop: ({ source }) => draggedSourceOf(source.data) !== null,
      getData: () => dropTargetData(latest.current.into),
    })
  )
}

/**
 * A row that drags, and that files whatever is dropped on it into `into`.
 * The panel decides what a drop does; the row only says where it lands.
 */
export function useRowDrag({
  rowRef,
  source,
  name,
  drag: { into, movable, takesFiles },
}: {
  rowRef: RefObject<HTMLLIElement | null>
  source: DraggedSource
  name: string
  drag: RowDrag
}) {
  // Read when a drag starts, so a rename re-registers nothing.
  const latest = useRef({ source, name, into })
  useEffect(() => {
    latest.current = { source, name, into }
  })

  useEffect(() => {
    const element = rowRef.current
    if (!element) return
    return combine(
      ...(takesFiles ? [takeFiles(element, latest)] : []),
      ...(movable ? [moveRows(element, latest)] : [])
    )
  }, [rowRef, movable, takesFiles])
}
