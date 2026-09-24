import { ThreadPrimitive } from "@assistant-ui/react"
import { useRef, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { ArrowDownIcon } from "@/components/ui/icons"
import {
  ScrollShadowEdge,
  useScrollShadowEdges,
} from "@/components/ui/scroll-shadow"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

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
  const viewportRef = useRef<HTMLDivElement>(null)
  const { edges, updateEdges } = useScrollShadowEdges(viewportRef)

  return (
    <div className="relative flex min-h-0 w-full min-w-0 flex-1 flex-col">
      <ThreadPrimitive.Viewport
        ref={viewportRef}
        turnAnchor="top"
        className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto px-4"
        style={{ scrollbarGutter: "stable" }}
        autoScroll
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
        scrollToBottomOnThreadSwitch
        data-chat-viewport
        onScroll={updateEdges}
      >
        {children}
        {footer ? (
          <ThreadPrimitive.ViewportFooter className="sticky bottom-0 z-20 -mx-4 mt-auto shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pb-1">
            <div className="relative mx-auto w-full max-w-2xl">
              <ScrollToBottom raised={footerHasNotice} />
              {footer}
            </div>
          </ThreadPrimitive.ViewportFooter>
        ) : null}
      </ThreadPrimitive.Viewport>
      <ScrollShadowEdge edge="top" visible={edges.top} from="from-background" />
    </div>
  )
}
