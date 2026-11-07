import { render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"

import { ChatErrorNotice } from "./chat-error-notice"

vi.mock("@assistant-ui/react", () => ({
  useAuiState: (
    select: (state: { message: { id: string; status: object } }) => unknown
  ) =>
    select({
      message: {
        id: "reply",
        status: {
          type: "incomplete",
          reason: "error",
          error: {
            kind: "provider_refused",
            message: "Insufficient account funds",
            provider: "openai_compatible",
            retryable: true,
          },
        },
      },
    }),
}))

it("offers another model, not a retry, when the provider refused", () => {
  render(
    <ChatErrorNotice
      onModelSetup={vi.fn()}
      onRetry={vi.fn()}
      onNewChat={vi.fn()}
    />
  )

  expect(screen.getByRole("alert").textContent).toContain(
    "The model provider refused this request: Insufficient account funds"
  )
  // The provider's words can hold a long address, which must not widen the notice.
  expect(screen.getByText(/refused this request/).className).toContain(
    "wrap-anywhere"
  )
  expect(screen.getByRole("button", { name: "Model setup" })).toBeTruthy()
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull()
})
