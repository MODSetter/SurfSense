import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"

import { cn } from "@/lib/utils"

export function ScrollShadow({
  children,
  className,
  viewportClassName,
}: {
  children: ReactNode
  className?: string
  viewportClassName?: string
}) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ top: false, bottom: false })
  const updateEdges = useCallback(() => {
    const viewport = viewportRef.current
    if (!viewport) {
      return
    }
    const top = viewport.scrollTop > 1
    const bottom =
      viewport.scrollTop + viewport.clientHeight < viewport.scrollHeight - 1
    setEdges((current) =>
      current.top === top && current.bottom === bottom
        ? current
        : { top, bottom }
    )
  }, [])

  useEffect(() => {
    const frame = window.requestAnimationFrame(updateEdges)
    const viewport = viewportRef.current
    if (typeof ResizeObserver === "undefined" || !viewport) {
      return () => window.cancelAnimationFrame(frame)
    }
    const observer = new ResizeObserver(updateEdges)
    observer.observe(viewport)
    if (viewport.firstElementChild) {
      observer.observe(viewport.firstElementChild)
    }
    return () => {
      window.cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [updateEdges])

  return (
    <div className={cn("relative min-h-0", className)}>
      <div
        ref={viewportRef}
        data-slot="scroll-shadow-viewport"
        className={cn(
          "h-full min-h-0 overflow-y-auto overscroll-contain",
          viewportClassName
        )}
        onScroll={updateEdges}
      >
        {children}
      </div>
      <div
        data-slot="scroll-shadow-top"
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 z-10 h-3 bg-gradient-to-b from-card to-transparent transition-opacity duration-100 ease-out",
          edges.top ? "opacity-100" : "opacity-0"
        )}
      />
      <div
        data-slot="scroll-shadow-bottom"
        className={cn(
          "pointer-events-none absolute inset-x-0 bottom-0 z-10 h-3 bg-gradient-to-t from-card to-transparent transition-opacity duration-100 ease-out",
          edges.bottom ? "opacity-100" : "opacity-0"
        )}
      />
    </div>
  )
}
