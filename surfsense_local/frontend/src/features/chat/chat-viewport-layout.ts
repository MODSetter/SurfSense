// The conversation's scroll area and its sticky composer footer, shared by
// ChatViewport and the startup frame, which draws them without the runtime.

export const THREAD_BODY_CLASS = "relative flex min-h-0 flex-1 flex-col"

export const VIEWPORT_BOX_CLASS =
  "relative flex min-h-0 w-full min-w-0 flex-1 flex-col"

// Top edge only: a bottom mask would fade the sticky composer.
export const VIEWPORT_CLASS =
  "flex min-h-0 w-full min-w-0 flex-1 scroll-fade-t flex-col overflow-y-auto px-4 [--scroll-fade-reveal:24px] scroll-fade-6"

// The gutter moves the centred column on systems with classic scrollbars.
export const VIEWPORT_STYLE = { scrollbarGutter: "stable" } as const

export const VIEWPORT_FOOTER_CLASS =
  "sticky bottom-0 z-20 -mx-4 mt-auto shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pb-1"

export const VIEWPORT_FOOTER_INNER_CLASS = "relative mx-auto w-full max-w-3xl"
