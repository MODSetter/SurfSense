import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react"

import { cn } from "@/lib/utils"

export function useScrollShadowEdges(
  viewportRef: RefObject<HTMLElement | null>
) {
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
  }, [viewportRef])

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
  }, [updateEdges, viewportRef])

  return { edges, updateEdges }
}

export function ScrollShadowEdge({
  edge,
  visible,
  from = "from-card",
}: {
  edge: "top" | "bottom"
  visible: boolean
  from?: "from-card" | "from-background"
}) {
  return (
    <div
      data-slot={edge === "top" ? "scroll-shadow-top" : "scroll-shadow-bottom"}
      className={cn(
        "pointer-events-none absolute inset-x-0 z-10 h-3 to-transparent transition-opacity duration-100 ease-out",
        edge === "top" ? "top-0 bg-gradient-to-b" : "bottom-0 bg-gradient-to-t",
        from === "from-background" ? "from-background" : "from-card",
        visible ? "opacity-100" : "opacity-0"
      )}
    />
  )
}

export function ScrollShadow({
  children,
  className,
  viewportClassName,
  from,
}: {
  children: ReactNode
  className?: string
  viewportClassName?: string
  from?: "from-card" | "from-background"
}) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const { edges, updateEdges } = useScrollShadowEdges(viewportRef)

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
      <ScrollShadowEdge edge="top" visible={edges.top} from={from} />
      <ScrollShadowEdge edge="bottom" visible={edges.bottom} from={from} />
    </div>
  )
}
