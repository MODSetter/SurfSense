import type { ComponentProps, ReactNode } from "react"

import { ColumnHeader } from "@/components/ui/column-header"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

/**
 * The conversation's box and its header line, which the startup frame draws
 * empty. `heading` precedes the header; `headerProps` go on its line.
 */
export function ConversationColumn({
  heading,
  header,
  headerProps,
  children,
}: {
  heading?: ReactNode
  header?: ReactNode
  headerProps?: ComponentProps<"div">
  children: ReactNode
}) {
  return (
    <section
      className="flex h-full min-w-0 flex-col bg-background"
      aria-label={intl.formatMessage({
        id: "chat_thread_panel_conversation_aria",
        defaultMessage: "Conversation",
      })}
    >
      {heading}
      <header>
        <ColumnHeader
          {...headerProps}
          className={cn("px-5", headerProps?.className)}
        >
          {header}
        </ColumnHeader>
      </header>
      {children}
    </section>
  )
}
