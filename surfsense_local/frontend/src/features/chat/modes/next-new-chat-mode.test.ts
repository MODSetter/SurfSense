import { afterEach, describe, expect, it } from "vitest"

import type {
  ChatMode,
  ModelCapability,
} from "@/features/models/capability/api"
import type { ModelSelection } from "@/features/models/selection/api"
import { readStartupLayout } from "@/features/startup/startup-layout"

import { rememberNextNewChatMode } from "./next-new-chat-mode"

function model(defaultMode: ChatMode, agenticAllowed = true): ModelSelection {
  return {
    model_type: "text_gen",
    provider: "openai_compatible",
    connection_id: 1,
    name: "anthropic/claude-fable-5",
    updated_at: "2026-11-01T00:00:00Z",
    capability: {
      modes: {
        agentic_allowed: agenticAllowed,
        blocked: null,
        default_mode: defaultMode,
        reason: { code: "assumed", values: {} },
      },
    } as unknown as ModelCapability,
  }
}

afterEach(() => localStorage.clear())

describe("the next new chat's mode, for the startup frame", () => {
  it("offers mentions when the model opens new chats in Agentic", () => {
    rememberNextNewChatMode(model("agentic"))
    expect(readStartupLayout().mentions).toBe(true)
  })

  it("offers none when the model opens new chats in Q&A", () => {
    rememberNextNewChatMode(model("basic"))
    expect(readStartupLayout().mentions).toBe(false)
  })

  it("offers none when the model may not run Agentic chats", () => {
    rememberNextNewChatMode(model("agentic", false))
    expect(readStartupLayout().mentions).toBe(false)
  })

  it("offers none without a model", () => {
    rememberNextNewChatMode(model("agentic"))
    rememberNextNewChatMode(null)
    expect(readStartupLayout().mentions).toBe(false)
  })

  it("offers none before anything was remembered", () => {
    expect(readStartupLayout().mentions).toBe(false)
  })
})
