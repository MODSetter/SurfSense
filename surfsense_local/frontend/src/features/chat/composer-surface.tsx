import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type { ComponentProps } from "react"
import TextareaAutosize from "react-textarea-autosize"

import { cn } from "@/lib/utils"

import { composerTextClassName } from "./composer-text-class"

// The composer's shape, drawn by ChatComposer around assistant-ui's parts and
// by the startup frame on its own: the box it shows first is the box that
// stays. A new chat's composer is "center", a thread's "bottom".

export type ComposerPlacement = "center" | "bottom"

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
}: useRender.ComponentProps<"div"> & { placement: ComposerPlacement }) {
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
 * The startup frame's box: one line at rest, growing with its text, and solid
 * while the controls around it fade in.
 */
export function ComposerText({
  placement,
  className,
  ...props
}: useRender.ComponentProps<"textarea"> & { placement: ComposerPlacement }) {
  return useRender({
    defaultTagName: "textarea",
    render: <TextareaAutosize />,
    // Marked for the startup fade, which leaves it alone.
    state: { revealSteady: true },
    stateAttributesMapping: {
      revealSteady: () => ({ "data-reveal-steady": "" }),
    },
    props: mergeProps<"textarea">(
      {
        rows: 1,
        className: cn(composerTextClassName(placement), className),
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
