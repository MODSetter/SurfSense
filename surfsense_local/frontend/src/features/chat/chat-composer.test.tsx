import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react"

import { render } from "@/test-utils"

import { ChatComposer } from "./chat-composer"
import { QUESTION_MAX_CHARS } from "./question-limit"

const MODEL = {
  model_type: "text_gen" as const,
  provider: "llamacpp" as const,
  connection_id: null,
  name: "Qwen3-1.7B-Q4_K_M",
  updated_at: "2026-09-05T00:00:00Z",
}

function Harness() {
  const runtime = useLocalRuntime({ run: async () => ({ content: [] }) })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatComposer
        placement="center"
        model={MODEL}
        sourceCount={0}
        isRunning={false}
        providerAvailable
        onModelSetup={() => undefined}
        onModelSelected={() => undefined}
        readsImages={false}
      />
    </AssistantRuntimeProvider>
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("chat composer", () => {
  it("stops a question at its share of the window and says so", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    render(<Harness />)

    const input = screen.getByRole<HTMLTextAreaElement>("textbox", {
      name: "Message",
    })
    expect(screen.queryByRole("status")).toBeNull()
    await user.click(input)
    await user.paste("x".repeat(QUESTION_MAX_CHARS + 1))

    expect(input.value).toHaveLength(QUESTION_MAX_CHARS)
    expect(screen.getByRole("status").textContent).toContain("4,096")
  })
})
