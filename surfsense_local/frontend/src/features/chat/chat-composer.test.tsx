import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
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

function Harness({
  model = MODEL,
  onUploadSources,
}: {
  model?: ModelSelection
  onUploadSources?: (files: File[]) => void
}) {
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
        onUploadSources={onUploadSources}
      />
    </AssistantRuntimeProvider>
  )
}

async function openThinking(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    screen.getByRole("button", { name: "Add images, sources, and more" })
  )
  return screen.findByRole("menuitemcheckbox", { name: /^Thinking/ })
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

    const toggle = await openThinking(user)
    expect(toggle.getAttribute("aria-checked")).toBe("true")
    expect(readThinkingOn()).toBe(true)
    await user.click(toggle)

    expect(toggle.getAttribute("aria-checked")).toBe("false")
    expect(readThinkingOn()).toBe(false)

    first.unmount()
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )
    expect((await openThinking(user)).getAttribute("aria-checked")).toBe(
      "false"
    )
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

    const toggle = await openThinking(user)
    await user.click(toggle)

    expect(toggle.getAttribute("aria-checked")).toBe("false")
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

    const toggle = await openThinking(user)
    expect(toggle.getAttribute("aria-disabled")).toBe("true")
    expect(toggle.getAttribute("aria-checked")).toBe("true")
    await user.hover(toggle)
    await waitFor(() =>
      expect(
        screen.getAllByText("Only a local model can answer without thinking")
      ).toHaveLength(2)
    )
    await user.click(toggle)

    expect(readThinkingOn()).toBe(true)
  })

  it("uploads sources picked from the add menu", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const opened: HTMLInputElement[] = []
    vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(function (
      this: HTMLInputElement
    ) {
      opened.push(this)
    })
    const onUploadSources = vi.fn()
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness onUploadSources={onUploadSources} />
      </TooltipProvider>
    )

    await user.click(
      screen.getByRole("button", { name: "Add images, sources, and more" })
    )
    await user.click(
      await screen.findByRole("menuitem", { name: /^Upload sources/ })
    )

    expect(opened).toHaveLength(1)
    const file = new File(["notes"], "notes.md", { type: "text/markdown" })
    fireEvent.change(opened[0]!, { target: { files: [file] } })
    expect(onUploadSources).toHaveBeenCalledWith([file])
  })
})
