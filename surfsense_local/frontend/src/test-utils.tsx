import type { ReactElement } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import {
  render as testingLibraryRender,
  type RenderOptions,
} from "@testing-library/react"

import { createQueryClient } from "@/lib/query-client"

export function render(
  element: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  const client = createQueryClient()
  return testingLibraryRender(element, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
    ...options,
  })
}
