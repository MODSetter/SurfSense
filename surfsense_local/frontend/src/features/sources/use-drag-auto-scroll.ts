import { useEffect, type RefObject } from "react"
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine"
import { autoScrollForElements } from "@atlaskit/pragmatic-drag-and-drop-auto-scroll/element"
import { autoScrollForExternal } from "@atlaskit/pragmatic-drag-and-drop-auto-scroll/external"

/** Scrolls a list while a row or a file is dragged near its top or bottom. */
export function useDragAutoScroll(scroller: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const element = scroller.current
    if (!element) return
    return combine(
      autoScrollForElements({ element, getAllowedAxis: () => "vertical" }),
      autoScrollForExternal({ element, getAllowedAxis: () => "vertical" })
    )
  }, [scroller])
}
