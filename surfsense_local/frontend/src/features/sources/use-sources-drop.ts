import { useEffect, useRef, useState, type RefObject } from "react"
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine"
import {
  dropTargetForElements,
  monitorForElements,
} from "@atlaskit/pragmatic-drag-and-drop/element/adapter"
import {
  dropTargetForExternal,
  monitorForExternal,
} from "@atlaskit/pragmatic-drag-and-drop/external/adapter"
import { containsFiles } from "@atlaskit/pragmatic-drag-and-drop/external/file"

import { filesOfDrop } from "./folder-upload/dropped-files"
import type { UploadEntry } from "./folder-upload/upload-plan"
import {
  TOP,
  subtreeOf,
  type FolderKey,
  type SourceIndex,
} from "./tree/source-index"
import {
  draggedSourceOf,
  dropFolderOf,
  dropTargetData,
  type DraggedSource,
} from "./tree/tree-drag"

/** Whether moving this row into that folder changes anything and is allowed. */
function canMove(index: SourceIndex, source: DraggedSource, into: FolderKey) {
  if (source.kind === "document") {
    return index.folderOfDocument.get(source.id) !== into
  }
  if (index.parentOf.get(source.id) === into) return false
  return into === TOP || !subtreeOf(index, source.id).has(into)
}

type Location = {
  current: { dropTargets: { data: Record<string | symbol, unknown> }[] }
}
// The innermost target names the folder; the panel itself is the top level.
const intoOf = (location: Location) =>
  dropFolderOf(location.current.dropTargets[0]?.data)

/**
 * The panel takes dragged rows and files from the desktop. `filesOver` while
 * files are over it; `dropFolder` is the folder a drop would file into, for
 * the row to light up.
 */
export function useSourcesDrop({
  panelRef,
  index,
  onMove,
  onDropFiles,
}: {
  panelRef: RefObject<HTMLElement | null>
  index: SourceIndex
  onMove: (source: DraggedSource, into: FolderKey) => void
  // Absent, files are refused: the caller withholds it while an upload runs.
  onDropFiles?: (entries: UploadEntry[], into: FolderKey) => void
}) {
  const [filesOver, setFilesOver] = useState(false)
  const [dropFolder, setDropFolder] = useState<FolderKey | undefined>()
  const latest = useRef({ index, onMove, onDropFiles })
  useEffect(() => {
    latest.current = { index, onMove, onDropFiles }
  })

  useEffect(() => {
    const element = panelRef.current
    if (!element) return
    const validMove = (
      data: Record<string | symbol, unknown>,
      at: Location
    ) => {
      const source = draggedSourceOf(data)
      const into = intoOf(at)
      return source &&
        into !== undefined &&
        canMove(latest.current.index, source, into)
        ? { source, into }
        : null
    }
    const clear = () => setDropFolder(undefined)

    return combine(
      dropTargetForElements({
        element,
        canDrop: ({ source }) => draggedSourceOf(source.data) !== null,
        getData: () => dropTargetData(TOP),
        onDrop: ({ source, location }) => {
          const move = validMove(source.data, location)
          if (move) latest.current.onMove(move.source, move.into)
        },
      }),
      monitorForElements({
        canMonitor: ({ source }) => draggedSourceOf(source.data) !== null,
        onDropTargetChange: ({ source, location }) =>
          setDropFolder(validMove(source.data, location)?.into),
        onDrop: clear,
      }),
      dropTargetForExternal({
        element,
        canDrop: (args) => true ||
          latest.current.onDropFiles !== undefined && containsFiles(args),
        getData: () => dropTargetData(TOP),
        onDragEnter: () => setFilesOver(true),
        onDragLeave: () => setFilesOver(false),
        onDrop: ({ source, location }) => {
          setFilesOver(false)
          const into = intoOf(location) ?? TOP
          void filesOfDrop(source).then((entries) => {
            if (entries.length > 0) latest.current.onDropFiles?.(entries, into)
          })
        },
      }),
      monitorForExternal({
        canMonitor: containsFiles,
        onDropTargetChange: ({ location }) => setDropFolder(intoOf(location)),
        onDrop: clear,
      })
    )
  }, [panelRef])

  return { filesOver, dropFolder }
}
