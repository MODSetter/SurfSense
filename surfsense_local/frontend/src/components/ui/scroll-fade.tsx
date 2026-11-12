import type { ComponentProps, ReactNode } from "react"

import { cn } from "@/lib/utils"

// A mask, not a painted gradient, so the fade matches any surface behind it.
// Keep backgrounds on `className` (the wrapper): the mask fades the viewport's own.
export function ScrollFade({
  children,
  className,
  viewportClassName,
  scroll = true,
  orientation = "vertical",
  ...viewportProps
}: {
  children: ReactNode
  className?: string
  viewportClassName?: string
  // False when an ancestor already owns scrolling for this content (e.g. a
  // dialog section that scrolls its heading and body together). Renders
  // children at their natural height instead of a clipped, scrolling box.
  scroll?: boolean
  // Horizontal fades the start and end edges, for a row that scrolls sideways.
  orientation?: "vertical" | "horizontal"
} & Omit<ComponentProps<"div">, "children" | "className">) {
  // The rest, `ref` included, land on the viewport: it is the element that
  // scrolls, so it is the one a caller measures, labels or listens to.
  if (!scroll) {
    return (
      <div {...viewportProps} className={cn(viewportClassName)}>
        {children}
      </div>
    )
  }

  return (
    <div className={cn("relative min-h-0", className)}>
      <div
        {...viewportProps}
        data-slot="scroll-fade-viewport"
        className={cn(
          orientation === "horizontal"
            ? "scroll-fade-x overflow-x-auto overscroll-x-contain [--scroll-fade-reveal:24px] scroll-fade-6"
            : "h-full min-h-0 scroll-fade overflow-y-auto overscroll-contain [--scroll-fade-reveal:24px] scroll-fade-6",
          viewportClassName
        )}
      >
        {children}
      </div>
    </div>
  )
}
