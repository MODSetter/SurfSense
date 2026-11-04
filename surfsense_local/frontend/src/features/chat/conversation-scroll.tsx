import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"

import { cn } from "@/lib/utils"

// The conversation's body and scroll area, drawn by the thread panel around
// assistant-ui's parts and by the startup frame on its own.

/** Under the conversation's header, the rest of its height. */
export function ConversationBody({
  className,
  render,
  ...props
}: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps<"div">(
      { className: cn("relative flex min-h-0 flex-1 flex-col", className) },
      props
    ),
  })
}

/**
 * The scrolling column of messages, or a new chat's centred box. Its gutter
 * stays, so the centred column sits in one place with or without a scrollbar.
 */
export function ConversationScroll({
  className,
  style,
  render,
  ...props
}: useRender.ComponentProps<"div">) {
  const scroll = useRender({
    defaultTagName: "div",
    render,
    props: mergeProps<"div">(
      {
        // Top edge only: a bottom mask would fade the sticky composer.
        className: cn(
          "flex min-h-0 w-full min-w-0 flex-1 scroll-fade-t flex-col overflow-y-auto px-4 [--scroll-fade-reveal:24px] scroll-fade-6",
          className
        ),
        style: { scrollbarGutter: "stable", ...style },
      },
      props
    ),
  })
  return (
    <div className="relative flex min-h-0 w-full min-w-0 flex-1 flex-col">
      {scroll}
    </div>
  )
}
