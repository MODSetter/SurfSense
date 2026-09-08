import { ThreadPrimitive } from "@assistant-ui/react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { ArrowDownIcon } from "@/components/ui/icons"

function ScrollToBottom() {
  return (
    <ThreadPrimitive.ScrollToBottom behavior="smooth" asChild>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className="absolute -top-10 left-1/2 -translate-x-1/2 rounded-full bg-card hover:bg-muted disabled:invisible dark:bg-card dark:hover:bg-muted"
        aria-label="Scroll to latest message"
      >
        <ArrowDownIcon />
      </Button>
    </ThreadPrimitive.ScrollToBottom>
  )
}

export function ChatViewport({
  children,
  footer,
}: {
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <ThreadPrimitive.Viewport
      turnAnchor="top"
      className="relative flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto px-4"
      style={{ scrollbarGutter: "stable" }}
      autoScroll
      scrollToBottomOnRunStart
      scrollToBottomOnInitialize
      scrollToBottomOnThreadSwitch
      data-chat-viewport
    >
      {children}
      {footer ? (
        <ThreadPrimitive.ViewportFooter className="sticky bottom-0 z-20 -mx-4 mt-auto shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pb-1">
          <div className="relative mx-auto w-full max-w-2xl">
            <ScrollToBottom />
            {footer}
          </div>
        </ThreadPrimitive.ViewportFooter>
      ) : null}
    </ThreadPrimitive.Viewport>
  )
}
