import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type { ComponentProps } from "react"

import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

// The `@` list's shape, drawn by SourceMentions around assistant-ui's popover
// and by the startup frame as a skeleton, so the list opens where the
// skeleton stood.

/** Above the composer's text; the real list then places itself at the `@`. */
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
          "absolute bottom-full left-1.5 z-50 mb-2 flex max-h-64 w-72 max-w-[calc(100%-0.75rem)] flex-col overflow-hidden rounded-xl border bg-popover p-1 text-popover-foreground shadow-md",
          className
        ),
      },
      props
    ),
  })
}

// One line: an icon, a name that gives way, and a detail at its end.
const ROW =
  "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm"

/** A row to pick. The popover's part renders through this with `asChild`, giving it
 *  its role, its highlight and its click. */
export function MentionRowButton({
  className,
  ...props
}: ComponentProps<typeof Button>) {
  return (
    <Button
      variant="bare"
      static
      // The message box keeps the focus, so typing goes on after a click.
      onMouseDown={(event) => event.preventDefault()}
      className={cn(ROW, "data-highlighted:bg-accent", className)}
      {...props}
    />
  )
}

/** A row's shape with nothing to pick yet, for the skeleton. */
export function MentionRowShape({
  className,
  ...props
}: ComponentProps<"div">) {
  return <div className={cn(ROW, className)} {...props} />
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
