import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react"
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip"

import { Tooltip, TooltipContent } from "@/components/ui/tooltip"

function isCutOff(element: HTMLElement | null) {
  return element !== null && element.scrollWidth > element.clientWidth
}

function isFocusVisible(element: Element) {
  try {
    return element.matches(":focus-visible")
  } catch {
    return true
  }
}

/**
 * The whole of a truncated text, over the element that cuts it off. It
 * opens only while the text is cut off, on hover or keyboard focus.
 */
function OverflowTooltip({
  label,
  render,
  focusOwner,
  side = "top",
}: {
  label: ReactNode
  // The element that truncates the text. It becomes the trigger.
  render: NonNullable<TooltipPrimitive.Trigger.Props["render"]>
  // A selector for the ancestor that takes keyboard focus for the text, such
  // as a tree row: focusing it opens the tooltip as well.
  focusOwner?: string
  side?: ComponentProps<typeof TooltipContent>["side"]
}) {
  const trigger = useRef<HTMLElement | null>(null)
  // Whatever element `render` is, not only the button Base UI types it as.
  const setTrigger = useCallback((node: HTMLElement | null) => {
    trigger.current = node
  }, [])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const owner = focusOwner
      ? trigger.current?.closest<HTMLElement>(focusOwner)
      : null
    if (!owner) return
    const onFocusIn = (event: FocusEvent) => {
      if (event.target instanceof Element && isFocusVisible(event.target)) {
        setOpen(isCutOff(trigger.current))
      }
    }
    const onFocusOut = (event: FocusEvent) => {
      const next = event.relatedTarget
      if (!(next instanceof Node && owner.contains(next))) setOpen(false)
    }
    owner.addEventListener("focusin", onFocusIn)
    owner.addEventListener("focusout", onFocusOut)
    return () => {
      owner.removeEventListener("focusin", onFocusIn)
      owner.removeEventListener("focusout", onFocusOut)
    }
  }, [focusOwner])

  // A drag sends no pointerleave, so the tooltip would stay over the row
  // being dragged away.
  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    window.addEventListener("dragstart", close, true)
    return () => window.removeEventListener("dragstart", close, true)
  }, [open])

  return (
    <Tooltip
      open={open}
      onOpenChange={(next) => setOpen(next && isCutOff(trigger.current))}
    >
      {/* Base UI's own trigger: the text already names the element, so it is
          not described again with the same words. */}
      <TooltipPrimitive.Trigger ref={setTrigger} render={render} />
      <TooltipContent
        side={side}
        collisionPadding={8}
        className="max-w-80 wrap-anywhere"
      >
        {label}
      </TooltipContent>
    </Tooltip>
  )
}

export { OverflowTooltip }
