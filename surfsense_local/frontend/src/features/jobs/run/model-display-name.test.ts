import { describe, expect, it } from "vitest"

import type { SelectableModel } from "@/features/models/chat-candidates/api"

import { displayModelName } from "./model-display-name"

const candidate = (
  name: string,
  display_name: string | null
): SelectableModel => ({
  name,
  display_name,
  installed: true,
  capabilities: ["text_gen"],
  types: ["text_gen"],
  selectable_for: ["text_gen"],
  provider: "llamacpp",
  connection_id: null,
})

describe("model display name", () => {
  it("names a model as the chat model picker does", () => {
    const candidates = [
      candidate("gemma.gguf", "Gemma 3 4B"),
      candidate("qwen3-4b.gguf", "Qwen3 4B"),
    ]

    expect(displayModelName("qwen3-4b.gguf", candidates)).toBe("Qwen3 4B")
  })

  it("keeps the name as sent when no candidate has a display name for it", () => {
    expect(
      displayModelName("m", [candidate("m", null), candidate("n", "N")])
    ).toBe("m")
    expect(displayModelName("gone.gguf", [candidate("m", "M")])).toBe(
      "gone.gguf"
    )
    expect(displayModelName("still-loading", undefined)).toBe("still-loading")
  })
})
