import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import { ReplyAnnouncer } from "./reply-announcer"

afterEach(cleanup)

const status = () => screen.getByRole("status").textContent

describe("ReplyAnnouncer", () => {
  it("says the model is working before anything has streamed", () => {
    render(<ReplyAnnouncer running answerStarted={false} />)

    expect(status()).toBe("Thinking")
  })

  it("stays quiet while the answer streams, so tokens never interrupt", () => {
    render(<ReplyAnnouncer running answerStarted />)

    expect(status()).toBe("")
  })

  it("says once that a reply it watched has finished", () => {
    const { rerender } = render(
      <ReplyAnnouncer running answerStarted={false} />
    )
    rerender(<ReplyAnnouncer running answerStarted />)
    rerender(<ReplyAnnouncer running={false} answerStarted />)

    expect(status()).toBe("Reply finished")
  })

  it("says nothing for a reply loaded from history", () => {
    render(<ReplyAnnouncer running={false} answerStarted />)

    expect(status()).toBe("")
  })

  it("says nothing when a turn ends with no answer", () => {
    // A failed or empty turn is announced by its error, not as a reply.
    const { rerender } = render(
      <ReplyAnnouncer running answerStarted={false} />
    )
    rerender(<ReplyAnnouncer running={false} answerStarted={false} />)

    expect(status()).toBe("")
  })
})
