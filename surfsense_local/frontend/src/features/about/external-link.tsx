import type { MouseEvent, ReactNode } from "react"

import { ExternalLinkIcon } from "@/components/ui/icons"

// The desktop app refuses in-app navigation, so a click goes to the OS
// browser through the bridge; a bare browser follows the href instead.
export function ExternalLink({
  href,
  children,
}: {
  href: string
  children: ReactNode
}) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (!window.surfsense?.openExternal) return
    event.preventDefault()
    void window.surfsense.openExternal(href)
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={onClick}
      className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground underline-offset-3 transition-colors hover:text-foreground hover:underline"
    >
      {children}
      <ExternalLinkIcon aria-hidden="true" className="size-3.5" />
    </a>
  )
}
