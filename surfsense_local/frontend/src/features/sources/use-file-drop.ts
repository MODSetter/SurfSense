import { useRef, useState, type DragEvent } from "react"

function carriesFiles(event: DragEvent) {
  return event.dataTransfer.types.includes("Files")
}

/**
 * A region that takes dropped files. `active` while files are dragged over it,
 * counted across child elements, since entering a child leaves the parent.
 */
export function useFileDrop(onDrop: ((files: File[]) => void) | undefined) {
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
          const files = Array.from(event.dataTransfer.files)
          if (files.length > 0) onDrop(files)
        },
      }
    : {}

  return { active: onDrop ? active : false, handlers }
}
