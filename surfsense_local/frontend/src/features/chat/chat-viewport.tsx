import { ThreadPrimitive } from "@assistant-ui/react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { ArrowDownIcon } from "@/components/ui/icons"

function ScrollToBottom() {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className="absolute -top-10 left-1/2 -translate-x-1/2 rounded-full bg-background disabled:invisible"
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
    <>
      <ThreadPrimitive.Viewport
        className="relative flex min-h-0 flex-1 flex-col overflow-y-auto"
        style={{ scrollbarGutter: "stable" }}
        autoScroll
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
        scrollToBottomOnThreadSwitch
        data-chat-viewport
      >
        {children}
      </ThreadPrimitive.Viewport>
      {footer ? (
        <div className="relative z-20 shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pt-7 pb-2">
          <div className="relative mx-auto w-full max-w-3xl">
            <ScrollToBottom />
            {footer}
          </div>
        </div>
      ) : null}
    </>
  )
}
