import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

// A mask, not a painted gradient, so the fade matches any surface behind it.
// Keep backgrounds on `className` (the wrapper): the mask fades the viewport's own.
export function ScrollFade({
  children,
  className,
  viewportClassName,
  scroll = true,
}: {
  children: ReactNode
  className?: string
  viewportClassName?: string
  // False when an ancestor already owns scrolling for this content (e.g. a
  // dialog section that scrolls its heading and body together). Renders
  // children at their natural height instead of a clipped, scrolling box.
  scroll?: boolean
}) {
  if (!scroll) {
    return <div className={cn(viewportClassName)}>{children}</div>
  }

  return (
    <div className={cn("relative min-h-0", className)}>
      <div
        data-slot="scroll-fade-viewport"
        className={cn(
          "h-full min-h-0 scroll-fade overflow-y-auto overscroll-contain [--scroll-fade-reveal:24px] scroll-fade-6",
          viewportClassName
        )}
      >
        {children}
      </div>
    </div>
  )
}
