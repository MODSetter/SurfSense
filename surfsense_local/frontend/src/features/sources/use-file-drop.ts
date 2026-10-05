import { useRef, useState, type DragEvent } from "react"

import { filesOfDrop } from "./folder-upload/dropped-files"
import type { UploadEntry } from "./folder-upload/upload-plan"

// A folder row marks itself as a drop target; anywhere else is the top level.
export const DROP_FOLDER_ATTRIBUTE = "data-drop-folder"

function dropFolderOf(event: DragEvent): number | null {
  const target = event.target instanceof Element ? event.target : null
  const value = target
    ?.closest(`[${DROP_FOLDER_ATTRIBUTE}]`)
    ?.getAttribute(DROP_FOLDER_ATTRIBUTE)
  return value ? Number(value) : null
}

export function carriesFiles(event: DragEvent) {
  return event.dataTransfer.types.includes("Files")
}

/**
 * A region that takes dropped files and folders. `active` while files are
 * dragged over it, counted across child elements, since entering a child
 * leaves the parent.
 */
export function useFileDrop(
  onDrop:
    ((entries: UploadEntry[], folderId: number | null) => void) | undefined
) {
  const [active, setActive] = useState(false)
  const depth = useRef(0)

  const reset = () => {
    depth.current = 0
    setActive(false)
  }

  const handlers = onDrop
    ? {
        onDragEnter: (event: DragEvent) => {
          if (!carriesFiles(event)) return
          depth.current += 1
          setActive(true)
        },
        onDragOver: (event: DragEvent) => {
          if (!carriesFiles(event)) return
          // Claims the drop, so the window-wide guard leaves it to this region.
          event.preventDefault()
          event.dataTransfer.dropEffect = "copy"
        },
        onDragLeave: (event: DragEvent) => {
          if (!carriesFiles(event)) return
          depth.current = Math.max(0, depth.current - 1)
          if (depth.current === 0) setActive(false)
        },
        onDrop: (event: DragEvent) => {
          if (!carriesFiles(event)) return
          event.preventDefault()
          reset()
          void filesOfDrop(event.dataTransfer).then((entries) => {
            if (entries.length > 0) onDrop(entries, dropFolderOf(event))
          })
        },
      }
    : {}

  return { active: onDrop ? active : false, handlers }
}
