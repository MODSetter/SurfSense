import { expect, it } from "vitest"

import { translatedChatError } from "./chat-error-text"

it("shows what the provider said when no retry can fix its refusal", () => {
  expect(
    translatedChatError({
      kind: "provider_refused",
      message: "Insufficient account funds",
      provider: "openai_compatible",
    })
  ).toBe("The model provider refused this request: Insufficient account funds")
})

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
