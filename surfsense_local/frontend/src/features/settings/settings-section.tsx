import type { ReactNode } from "react"

import { ScrollShadow } from "@/components/ui/scroll-shadow"

export function SettingsSection({
  title,
  description,
  children,
  footer,
  scrollable = true,
}: {
  title: string
  description: string
  children: ReactNode
  footer?: ReactNode
  scrollable?: boolean
}) {
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
        {scrollable ? (
          <ScrollShadow
            className="h-full"
            viewportClassName="px-7 py-5"
          >
            <div>{children}</div>
          </ScrollShadow>
        ) : (
          <div
            data-slot="settings-section-content"
            className="h-full min-h-0 overflow-hidden px-7 py-5"
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
