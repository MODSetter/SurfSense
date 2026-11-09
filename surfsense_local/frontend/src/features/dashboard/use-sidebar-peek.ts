import { useCallback, useEffect, useRef, useState, type RefObject } from "react"

// A pointer crossing the edge on its way elsewhere does not open the sidebar.
const OPEN_DELAY_MS = 120
// Long enough to cross the 56 px workspace rail from the window's own edge.
const CLOSE_DELAY_MS = 300

export const REVEAL_EDGE_SLOT = "sidebar-reveal-edge"

// A menu or dialog it opened, or typing in it: moving away must not take it.
function isInUse(panel: HTMLElement | null) {
  if (!panel) return false
  if (panel.querySelector("[data-popup-open]")) return true
  if (document.querySelector('[role="dialog"],[role="alertdialog"]')) {
    return true
  }
  const active = document.activeElement
  return (
    active instanceof HTMLElement &&
    panel.contains(active) &&
    active.matches("input,textarea,[contenteditable='true']")
  )
}

/** Floats a hidden sidebar in while the pointer is at the edge or over it. */
export function useSidebarPeek(
  panelRef: RefObject<HTMLElement | null>,
  enabled: boolean
) {
  const [peeking, setPeeking] = useState(false)
  if (!enabled && peeking) setPeeking(false)
  const openTimer = useRef<number | undefined>(undefined)

  const cancelOpen = useCallback(() => {
    window.clearTimeout(openTimer.current)
  }, [])
  const openSoon = useCallback(() => {
    window.clearTimeout(openTimer.current)
    openTimer.current = window.setTimeout(() => setPeeking(true), OPEN_DELAY_MS)
  }, [])
  useEffect(() => cancelOpen, [cancelOpen])
  // The edge unmounts while the sidebar shows, so no pointer leave cancels it.
  useEffect(() => {
    if (!enabled) cancelOpen()
  }, [enabled, cancelOpen])

  useEffect(() => {
    if (!peeking) return
    let closeTimer: number | undefined
    const closeWhenFree = () => {
      closeTimer = isInUse(panelRef.current)
        ? window.setTimeout(closeWhenFree, CLOSE_DELAY_MS)
        : undefined
      if (closeTimer === undefined) setPeeking(false)
    }
    // Read from the document, as a menu or dialog it opens lies outside it.
    const follow = (event: Event) => {
      const target = event.target
      const inside =
        target instanceof Element &&
        (panelRef.current?.contains(target) ||
          target.closest(`[data-slot="${REVEAL_EDGE_SLOT}"]`) !== null)
      if (inside) {
        window.clearTimeout(closeTimer)
        closeTimer = undefined
      } else if (closeTimer === undefined) {
        closeTimer = window.setTimeout(closeWhenFree, CLOSE_DELAY_MS)
      }
    }
    // Leaving the window past the edge, its likeliest exit, moves nothing inside it.
    const leaveWindow = (event: MouseEvent) => {
      if (event.relatedTarget === null && closeTimer === undefined) {
        closeTimer = window.setTimeout(closeWhenFree, CLOSE_DELAY_MS)
      }
    }
    document.addEventListener("pointermove", follow, { passive: true })
    document.addEventListener("dragover", follow, { passive: true })
    document.addEventListener("mouseout", leaveWindow)
    return () => {
      window.clearTimeout(closeTimer)
      document.removeEventListener("pointermove", follow)
      document.removeEventListener("dragover", follow)
      document.removeEventListener("mouseout", leaveWindow)
    }
  }, [peeking, panelRef])

  return {
    peeking,
    edgeProps: {
      "data-slot": REVEAL_EDGE_SLOT,
      "aria-hidden": true,
      onPointerEnter: openSoon,
      onPointerLeave: cancelOpen,
      // Files dragged in can reach the sources list and its folders.
      onDragEnter: openSoon,
    },
  }
}
