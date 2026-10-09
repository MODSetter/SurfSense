import { useEffect, useRef, useState, type KeyboardEvent } from "react"

import { cn } from "@/lib/utils"

// How far one arrow press moves the edge.
const KEY_STEP = 16

/**
 * The draggable edge between two columns. It holds no width of its own: it
 * reports one inside `min` and `max`, and its owner keeps it.
 */
function ResizeHandle({
  side,
  value,
  min,
  max,
  label,
  controls,
  onValueChange,
  onValueCommitted,
  onReset,
  onDraggingChange,
  className,
}: {
  // The side of the layout the resized column is on: a column at the start
  // grows as its edge moves right, one at the end as it moves left.
  side: "start" | "end"
  value: number
  min: number
  max: number
  label: string
  controls?: string
  // Each step of a drag.
  onValueChange: (value: number) => void
  // A finished drag or a key press: the width to keep.
  onValueCommitted: (value: number) => void
  // A double-click, back to the column's default.
  onReset: () => void
  onDraggingChange?: (dragging: boolean) => void
  className?: string
}) {
  const drag = useRef<{ x: number; from: number; last: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  const grows = side === "start" ? 1 : -1
  const clamp = (width: number) =>
    Math.round(Math.min(Math.max(width, min), max))

  // A fast drag outruns the handle: the whole page keeps its cursor and
  // selects no text until the pointer is let go.
  useEffect(() => {
    if (!dragging) return
    const { cursor, userSelect } = document.body.style
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    return () => {
      document.body.style.cursor = cursor
      document.body.style.userSelect = userSelect
    }
  }, [dragging])

  const endDrag = () => {
    const ended = drag.current
    if (!ended) return
    drag.current = null
    setDragging(false)
    onDraggingChange?.(false)
    if (ended.last !== ended.from) onValueCommitted(ended.last)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    let next: number
    switch (event.key) {
      case "ArrowLeft":
        next = value - grows * KEY_STEP
        break
      case "ArrowRight":
        next = value + grows * KEY_STEP
        break
      case "Home":
        next = min
        break
      case "End":
        next = max
        break
      default:
        return
    }
    event.preventDefault()
    const width = clamp(next)
    if (width !== value) onValueCommitted(width)
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-controls={controls}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      data-slot="resize-handle"
      data-dragging={dragging || undefined}
      // Takes no room: it overhangs both columns by half its width.
      className={cn(
        "relative z-10 -mx-1 w-2 shrink-0 cursor-col-resize touch-none outline-none select-none after:pointer-events-none after:absolute after:inset-y-0 after:left-1/2 after:w-0.5 after:-translate-x-1/2 after:transition-colors after:duration-150 hover:after:bg-ring/40 focus-visible:after:bg-ring data-dragging:after:bg-ring/60 motion-reduce:after:transition-none",
        className
      )}
      onPointerDown={(event) => {
        if (event.button !== 0) return
        // No text selection and no focus: a drag leaves focus where it was.
        event.preventDefault()
        event.currentTarget.setPointerCapture(event.pointerId)
        drag.current = { x: event.clientX, from: value, last: value }
        setDragging(true)
        onDraggingChange?.(true)
      }}
      onPointerMove={(event) => {
        const current = drag.current
        if (!current) return
        const width = clamp(current.from + grows * (event.clientX - current.x))
        if (width === current.last) return
        current.last = width
        onValueChange(width)
      }}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onLostPointerCapture={endDrag}
      onDoubleClick={onReset}
      onKeyDown={onKeyDown}
    />
  )
}

export { ResizeHandle }
