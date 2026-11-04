import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type { ComponentProps } from "react"

import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

// The `@` list's shape, drawn by SourceMentions around assistant-ui's popover
// and by the startup frame as a skeleton, so the list opens where the
// skeleton stood.

/** Above the composer's text, the width of its box. */
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
          id: "chat_mentions_list_aria",
          defaultMessage: "Sources and artifacts",
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

/** One row, on one line: an icon, a name that gives way, and a detail at its end. */
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
        // The message box keeps the focus, so typing goes on after a click.
        onMouseDown: (event) => event.preventDefault(),
        className: cn(
          "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm outline-none",
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
      className={cn(
        "ml-auto max-w-[45%] shrink-0 truncate pl-2 text-xs text-muted-foreground",
        className
      )}
      {...props}
    />
  )
}
