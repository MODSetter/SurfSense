import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"

import { cn } from "@/lib/utils"

export function SettingsSection({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description: string
  children: ReactNode
  footer?: ReactNode
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [scrollEdges, setScrollEdges] = useState({
    top: false,
    bottom: false,
  })
  const updateScrollEdges = useCallback(() => {
    const scrollArea = scrollRef.current
    if (!scrollArea) {
      return
    }
    const top = scrollArea.scrollTop > 1
    const bottom =
      scrollArea.scrollTop + scrollArea.clientHeight <
      scrollArea.scrollHeight - 1
    setScrollEdges((current) =>
      current.top === top && current.bottom === bottom
        ? current
        : { top, bottom }
    )
  }, [])

  useEffect(() => {
    updateScrollEdges()
    if (typeof ResizeObserver === "undefined") {
      return
    }
    const observer = new ResizeObserver(updateScrollEdges)
    const scrollArea = scrollRef.current
    if (scrollArea) {
      observer.observe(scrollArea)
      const content = scrollArea.firstElementChild
      if (content) {
        observer.observe(content)
      }
    }
    return () => observer.disconnect()
  }, [updateScrollEdges])

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)_auto]">
      <header className="px-7 pt-10 pb-6">
        <h2 className="font-heading text-lg font-medium text-balance">
          {title}
        </h2>
        <p className="mt-1 text-sm text-pretty text-muted-foreground">
          {description}
        </p>
      </header>

      <div className="relative min-h-0">
        <div
          ref={scrollRef}
          data-slot="settings-section-scroll"
          className="h-full min-h-0 overflow-y-auto overscroll-contain px-7 py-5"
          onScroll={updateScrollEdges}
        >
          <div>{children}</div>
        </div>
        <div
          data-slot="settings-section-shadow-top"
          className={cn(
            "pointer-events-none absolute inset-x-0 top-0 z-10 h-3 bg-gradient-to-b from-popover to-transparent transition-opacity duration-200 ease-out",
            scrollEdges.top ? "opacity-100" : "opacity-0"
          )}
        />
        <div
          data-slot="settings-section-shadow-bottom"
          className={cn(
            "pointer-events-none absolute inset-x-0 bottom-0 z-10 h-3 bg-gradient-to-t from-popover to-transparent transition-opacity duration-200 ease-out",
            scrollEdges.bottom ? "opacity-100" : "opacity-0"
          )}
        />
      </div>

      {footer ? (
        <footer className="flex justify-end border-t bg-popover px-7 py-4">
          {footer}
        </footer>
      ) : null}
    </div>
  )
}
