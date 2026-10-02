import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"

import { render } from "@/test-utils"

import { ReplyAnnouncer } from "./reply-announcer"

afterEach(cleanup)

const status = () => screen.getByRole("status").textContent

describe("ReplyAnnouncer", () => {
  it("says the model is working before anything has streamed", async () => {
    render(<ReplyAnnouncer running answerStarted={false} completed={false} />)

    // Mounted empty first: a status region born with text is often not read.
    expect(status()).toBe("")
    await waitFor(() => expect(status()).toBe("Thinking"))
  })

  it("stays quiet while the answer streams, so tokens never interrupt", () => {
    render(<ReplyAnnouncer running answerStarted completed={false} />)

    expect(status()).toBe("")
  })

  it("says once that a reply it watched has finished", async () => {
    const { rerender } = render(
      <ReplyAnnouncer running answerStarted={false} completed={false} />
    )
    rerender(<ReplyAnnouncer running answerStarted completed={false} />)
    rerender(<ReplyAnnouncer running={false} answerStarted completed />)

    await waitFor(() => expect(status()).toBe("Reply finished"))
  })

  it("says nothing for a reply loaded from history", () => {
    render(<ReplyAnnouncer running={false} answerStarted completed />)

    expect(status()).toBe("")
  })

  it("says nothing when a turn ends with no answer", () => {
    // A failed or empty turn is announced by its error, not as a reply.
    const { rerender } = render(
      <ReplyAnnouncer running answerStarted={false} completed={false} />
    )
    rerender(
      <ReplyAnnouncer running={false} answerStarted={false} completed={false} />
    )

    expect(status()).toBe("")
  })

  it("says nothing for a reply stopped or failed after it started", () => {
    // Its alert, or the stop the person chose, already says so.
    const { rerender } = render(
      <ReplyAnnouncer running answerStarted completed={false} />
    )
    rerender(<ReplyAnnouncer running={false} answerStarted completed={false} />)

    expect(status()).toBe("")
  })
})
