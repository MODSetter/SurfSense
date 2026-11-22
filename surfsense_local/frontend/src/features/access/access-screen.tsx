import type { ReactNode, SubmitEvent } from "react"

import surfSenseLogo from "@/surfsense-logo.svg"

/** The logo, a title and a line, above a sign-in's or a setup's form. */
export function AccessScreen({
  title,
  body,
  onSubmit,
  children,
}: {
  title: string
  body: string
  onSubmit?: (event: SubmitEvent) => void
  children?: ReactNode
}) {
  const head = (
    <div className="flex flex-col items-center gap-3 text-center">
      <span
        aria-hidden="true"
        className="size-10 bg-foreground"
        style={{
          maskImage: `url(${surfSenseLogo})`,
          maskPosition: "center",
          maskRepeat: "no-repeat",
          maskSize: "contain",
        }}
      />
      <h1 className="text-xl font-semibold text-balance">{title}</h1>
      <p className="text-sm text-pretty text-muted-foreground">{body}</p>
    </div>
  )
  return (
    // The words are a screen's, not content to copy; the field stays selectable.
    <main className="flex h-full items-center justify-center bg-app-shell p-8 select-none">
      {onSubmit ? (
        <form
          className="flex w-full max-w-sm flex-col gap-6"
          onSubmit={onSubmit}
        >
          {head}
          {children}
        </form>
      ) : (
        <div className="flex w-full max-w-sm flex-col gap-6">{head}</div>
      )}
    </main>
  )
}
