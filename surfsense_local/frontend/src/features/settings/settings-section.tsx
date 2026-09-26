import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { ArrowLeftIcon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"

export function SettingsSection({
  title,
  description,
  children,
  footer,
  back,
  scrollable = true,
}: {
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  /** A sub-page names the page it returns to. */
  back?: { label: string; onClick: () => void }
  // true: header fixed, only the content below it scrolls (most sections).
  // false: nothing here scrolls — the content manages its own scroll area(s).
  // "all": header and content scroll together as one region, for content
  // whose height varies too much for a fixed header to make sense.
  scrollable?: boolean | "all"
}) {
  const heading = (
    <>
      {back ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mb-2 -ml-2 text-muted-foreground"
          onClick={back.onClick}
        >
          <ArrowLeftIcon data-icon="inline-start" />
          {back.label}
        </Button>
      ) : null}
      <h2 className="font-heading text-lg font-medium text-balance">{title}</h2>
      {description ? (
        <p className="mt-1 text-sm text-pretty text-muted-foreground">
          {description}
        </p>
      ) : null}
    </>
  )

  if (scrollable === "all") {
    return (
      <div className="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_auto]">
        {/* pt-10 is a fixed gutter, not scroll content — it keeps the dialog's own close button clear no matter how far this scrolls, the way the fixed header used to in the other two modes; min-w-0 stops a wide nowrap descendant from forcing this grid item past its 1fr track and out through the section's overflow-hidden. */}
        <div className="min-h-0 min-w-0 pt-10">
          <ScrollFade className="h-full" viewportClassName="px-7 pb-5">
            <header className="pb-6">{heading}</header>
            {children}
          </ScrollFade>
        </div>

        {footer ? (
          <footer className="flex justify-end border-t bg-popover px-7 py-4">
            {footer}
          </footer>
        ) : null}
      </div>
    )
  }

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)_auto]">
      <header className="px-7 pt-10 pb-6">{heading}</header>

      <div className="relative min-h-0 min-w-0">
        {scrollable ? (
          <ScrollFade className="h-full" viewportClassName="px-7 py-5">
            <div>{children}</div>
          </ScrollFade>
        ) : (
          <div
            data-slot="settings-section-content"
            className="h-full min-h-0 overflow-hidden px-7 pt-5"
          >
            <div className="h-full min-h-0">{children}</div>
          </div>
        )}
      </div>

      {footer ? (
        <footer className="flex justify-end border-t bg-popover px-7 py-4">
          {footer}
        </footer>
      ) : null}
    </div>
  )
}
