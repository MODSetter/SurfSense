import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type { ComponentProps } from "react"
import TextareaAutosize from "react-textarea-autosize"

import { cn } from "@/lib/utils"

// The composer's shape, drawn by ChatComposer around assistant-ui's parts and
// by the startup frame on its own: the box it shows first is the box that
// stays. A new chat's composer is "center", a thread's "bottom".

type Placement = "center" | "bottom"

/** The column the composer sits in, with what goes above and below its box. */
export function ComposerColumn({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("relative mx-auto w-full max-w-2xl", className)}
      {...props}
    />
  )
}

/** The bordered box. ChatComposer renders it as the composer's form. */
export function ComposerBox({
  placement,
  className,
  render,
  ...props
}: useRender.ComponentProps<"div"> & { placement: Placement }) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps<"div">(
      {
        // No top padding: text scrolls up to the border, not to a strip above
        // it, and holds that space in its own padding instead.
        className: cn(
          "relative rounded-2xl border bg-card px-1.5 pb-1.5 shadow-sm",
          placement === "bottom" && "flex items-end gap-2",
          className
        ),
      },
      props
    ),
  })
}

/**
 * The text box: one line at rest, growing with its text. ChatComposer renders
 * it as assistant-ui's input; on its own it is the autosizing textarea that
 * input is built on, so the startup frame's box grows exactly as the
 * composer's does, in every browser. It stays solid while the controls
 * around it fade in at startup.
 */
export function ComposerText({
  placement,
  className,
  render,
  ...props
}: useRender.ComponentProps<"textarea"> & { placement: Placement }) {
  return useRender({
    defaultTagName: "textarea",
    render: render ?? <TextareaAutosize />,
    // Marked for the startup fade, which leaves it alone.
    state: { revealSteady: true },
    stateAttributesMapping: {
      revealSteady: () => ({ "data-reveal-steady": "" }),
    },
    props: mergeProps<"textarea">(
      {
        rows: 1,
        className: cn(
          "max-h-44 resize-none bg-transparent px-2 pt-4 pb-2.5 text-sm outline-none placeholder:text-muted-foreground",
          placement === "center" ? "block min-h-12 w-full" : "min-h-10 flex-1",
          className
        ),
      },
      props
    ),
  })
}

/**
 * A new chat's row of controls under its text. At least as tall as its
 * icon-lg buttons, so the startup frame's, which has none, matches.
 */
export function ComposerControls({
  className,
  ...props
}: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex min-h-9 items-center justify-between gap-2",
        className
      )}
      {...props}
    />
  )
}
