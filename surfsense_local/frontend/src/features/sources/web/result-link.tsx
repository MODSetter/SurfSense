import type { ComponentProps, MouseEvent } from "react"

import { cn } from "@/lib/utils"

// The desktop app refuses in-app navigation, so a click goes to the OS
// browser through the bridge; a bare browser follows the href instead.
export function ResultLink({
  href,
  className,
  ...props
}: ComponentProps<"a"> & { href: string }) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (!window.surfsense?.openExternal) return
    event.preventDefault()
    void window.surfsense.openExternal(href)
  }
  return (
    <a
      {...props}
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={onClick}
      className={cn(
        "underline-offset-3 transition-colors hover:text-foreground hover:underline",
        className
      )}
    />
  )
}
