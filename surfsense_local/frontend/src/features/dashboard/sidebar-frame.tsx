import type { ReactNode } from "react"

import { ColumnHeader } from "@/components/ui/column-header"

/**
 * The left column's box and its "SurfSense" heading, which never change, so
 * the startup frame draws them too. `nav` sits under the heading in its header.
 */
export function SidebarFrame({
  headerStart,
  nav,
  children,
}: {
  headerStart?: ReactNode
  nav?: ReactNode
  children?: ReactNode
}) {
  return (
    <aside className="flex h-full min-w-0 flex-col border-r bg-background select-none">
      <header>
        <ColumnHeader>
          {headerStart}
          <h2 className="truncate px-1 brand-wordmark text-xl text-foreground select-none">
            SurfSense
          </h2>
        </ColumnHeader>
        {nav}
      </header>
      {children}
    </aside>
  )
}
