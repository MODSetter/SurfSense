import { ThreadPrimitive } from "@assistant-ui/react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { ArrowDownIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import {
  VIEWPORT_BOX_CLASS,
  VIEWPORT_CLASS,
  VIEWPORT_FOOTER_CLASS,
  VIEWPORT_FOOTER_INNER_CLASS,
  VIEWPORT_STYLE,
} from "./chat-viewport-layout"

// Raised clear of a notice tucked behind the composer's top edge, whose visible
// part is about 28px tall.
function ScrollToBottom({ raised }: { raised: boolean }) {
  return (
    <ThreadPrimitive.ScrollToBottom behavior="smooth" asChild>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className={cn(
          "absolute left-1/2 -translate-x-1/2 rounded-full bg-card hover:bg-muted disabled:invisible dark:bg-card dark:hover:bg-muted",
          raised ? "-top-17" : "-top-10"
        )}
        aria-label={intl.formatMessage({
          id: "chat_viewport_scroll_to_latest_aria",
          defaultMessage: "Scroll to latest message",
        })}
      >
        <ArrowDownIcon />
      </Button>
    </ThreadPrimitive.ScrollToBottom>
  )
}

export function ChatViewport({
  children,
  footer,
  footerHasNotice = false,
}: {
  children: ReactNode
  footer?: ReactNode
  footerHasNotice?: boolean
}) {
  return (
    <div className={VIEWPORT_BOX_CLASS}>
      <ThreadPrimitive.Viewport
        turnAnchor="top"
        className={VIEWPORT_CLASS}
        style={VIEWPORT_STYLE}
        autoScroll
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
        scrollToBottomOnThreadSwitch
        data-chat-viewport
      >
        {children}
        {footer ? (
          <ThreadPrimitive.ViewportFooter className={VIEWPORT_FOOTER_CLASS}>
            <div className={VIEWPORT_FOOTER_INNER_CLASS}>
              <ScrollToBottom raised={footerHasNotice} />
              {footer}
            </div>
          </ThreadPrimitive.ViewportFooter>
        ) : null}
      </ThreadPrimitive.Viewport>
    </div>
  )
}
