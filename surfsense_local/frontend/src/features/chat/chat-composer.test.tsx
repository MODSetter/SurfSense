import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

import { ChatComposer } from "./chat-composer"
import { QUESTION_MAX_CHARS } from "./question-limit"
import { readThinkingOn } from "./thinking-preference"

const MODEL: ModelSelection = {
  model_type: "text_gen" as const,
  provider: "llamacpp" as const,
  connection_id: null,
  name: "Qwen3-1.7B-Q4_K_M",
  updated_at: "2026-09-05T00:00:00Z",
}

function Harness({ model = MODEL }: { model?: ModelSelection }) {
  const runtime = useLocalRuntime({ run: async () => ({ content: [] }) })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatComposer
        placement="center"
        model={model}
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
  localStorage.clear()
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

  it("turns thinking off for a local model and remembers it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    const first = render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )

    const toggle = screen.getByRole("button", { name: "Thinking" })
    expect(toggle.getAttribute("aria-pressed")).toBe("true")
    expect(readThinkingOn()).toBe(true)
    await user.click(toggle)

    expect(toggle.getAttribute("aria-pressed")).toBe("false")
    expect(readThinkingOn()).toBe(false)

    first.unmount()
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )
    expect(
      screen
        .getByRole("button", { name: "Thinking" })
        .getAttribute("aria-pressed")
    ).toBe("false")
  })

  it("sends what the switch shows when the choice cannot be stored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("full", "QuotaExceededError")
      })
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )

    const toggle = screen.getByRole("button", { name: "Thinking" })
    await user.click(toggle)

    expect(toggle.getAttribute("aria-pressed")).toBe("false")
    expect(readThinkingOn()).toBe(false)

    setItem.mockRestore()
    await user.click(toggle)
    expect(readThinkingOn()).toBe(true)
  })

  it("holds the thinking switch on for a model that cannot be told to stop", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness
          model={{ ...MODEL, provider: "openai_compatible", connection_id: 3 }}
        />
      </TooltipProvider>
    )

    const toggle = screen.getByRole("button", { name: "Thinking" })
    expect(toggle.getAttribute("aria-disabled")).toBe("true")
    expect(toggle.getAttribute("aria-pressed")).toBe("true")
    await user.click(toggle)

    expect(readThinkingOn()).toBe(true)
  })
})
