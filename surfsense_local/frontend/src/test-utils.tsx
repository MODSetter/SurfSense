import type { ReactElement } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import {
  render as testingLibraryRender,
  type RenderOptions,
} from "@testing-library/react"

import { TooltipProvider } from "@/components/ui/tooltip"
import { createQueryClient } from "@/lib/query-client"

export function render(
  element: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  const client = createQueryClient()
  return testingLibraryRender(element, {
    wrapper: ({ children }) => (
      // Mirrors main.tsx, where every component renders inside these.
      <QueryClientProvider client={client}>
        <TooltipProvider>{children}</TooltipProvider>
      </QueryClientProvider>
    ),
    ...options,
  })
}

/** What the message box reads: its text, each chip as its name. */
export function boxText(box: Element | null) {
  return (box?.textContent ?? "").replace(/\u200b/g, "")
}

/** Whether the message box refuses writing, as a disabled textarea would. */
export function boxHeld(box: Element | null) {
  return box?.getAttribute("contenteditable") !== "true"
}
