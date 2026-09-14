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
