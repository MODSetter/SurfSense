import { expect, it } from "vitest"

import { translatedChatError } from "./chat-error-text"

it("uses local detail only for failures caught before streaming", () => {
  expect(
    translatedChatError({
      kind: "unknown",
      message: "Provider crashed",
      provider: "",
      detailIsLocal: true,
    })
  ).toBe("Something went wrong generating a reply: Provider crashed")

  expect(
    translatedChatError({
      kind: "unknown",
      message: "Something went wrong generating a reply. Try again.",
      provider: "llamacpp",
    })
  ).toBe("Something went wrong generating a reply. Try again.")
})
