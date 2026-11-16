import type { ComponentProps, MouseEvent } from "react"

import { cn } from "@/lib/utils"

// A result's address comes from a scraped page, so a click asks first, in the
// app's link popup; the desktop app's openExternal drops every other site.
export function ResultLink({
  href,
  onOpen,
  className,
  ...props
}: ComponentProps<"a"> & { href: string; onOpen: () => void }) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    onOpen()
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
