import type { ReactNode } from "react"

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
  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)_auto]">
      <header className="border-b px-7 pt-10 pb-6">
        <h2 className="font-heading text-lg font-medium text-balance">
          {title}
        </h2>
        <p className="mt-1 text-sm text-pretty text-muted-foreground">
          {description}
        </p>
      </header>

      <div
        data-slot="settings-section-scroll"
        className="min-h-0 overflow-y-auto overscroll-contain px-7 py-5"
      >
        {children}
      </div>

      {footer ? (
        <footer className="flex justify-end border-t bg-popover px-7 py-4">
          {footer}
        </footer>
      ) : null}
    </div>
  )
}
