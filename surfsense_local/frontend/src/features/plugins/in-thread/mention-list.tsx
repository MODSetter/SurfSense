import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type { ComponentProps } from "react"

import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

// The `@` list's shape, drawn by PluginMentions around assistant-ui's popover
// and by the startup frame as a skeleton, so the list opens where the
// skeleton stood.

/** Above the composer's text, the width of its box. Named "Plugins". */
export function MentionList({
  className,
  render,
  ...props
}: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps<"div">(
      {
        "aria-label": intl.formatMessage({
          id: "plugins_mentions_aria",
          defaultMessage: "Plugins",
        }),
        className: cn(
          "absolute inset-x-1.5 bottom-full z-50 mb-2 max-h-64 overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-md",
          className
        ),
      },
      props
    ),
  })
}

/** A plugin's row: its name, then a line about it. */
export function MentionItem({
  className,
  render,
  ...props
}: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps<"div">(
      {
        className: cn(
          "flex w-full flex-col items-start gap-0.5 rounded-lg px-2 py-1.5 text-left text-sm outline-none",
          className
        ),
      },
      props
    ),
  })
}

export function MentionItemDescription({
  className,
  ...props
}: ComponentProps<"span">) {
  return (
    <span
      className={cn("line-clamp-1 text-xs text-muted-foreground", className)}
      {...props}
    />
  )
}
