import type { ComponentProps } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { fakeMicrophone } from "@/features/dictation/capture/fake-microphone"
import {
  createDictation,
  type Dictation,
} from "@/features/dictation/dictation-adapter"
import {
  fakeDictationApi,
  held,
  said,
} from "@/features/dictation/fake-dictation-api"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

import type { ChatMessage } from "./api"
import { AssistantMessage } from "./message"
import { ThreadPanel } from "./thread-panel"

vi.mock("./message", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./message")>()
  return { ...actual, AssistantMessage: vi.fn(actual.AssistantMessage) }
})

const THREAD = {
  id: 1,
  workspace_id: 1,
  title: "Revenue",
  uses_agent: false,
  created_at: "2026-10-05T00:00:00Z",
  updated_at: "2026-10-05T00:00:00Z",
}

function turn(
  id: number,
  role: "user" | "assistant",
  text: string,
  ending?: ChatMessage["content"]["ending"]
): ChatMessage {
  return {
    id,
    role,
    content: { text, citations: [], ...(ending ? { ending } : {}) },
    created_at: "2026-10-05T00:00:00Z",
    completed_at: role === "assistant" ? "2026-10-05T00:00:01Z" : null,
  }
}

// Three finished turns, the last one failed and so offering Retry.
const HISTORY = [
  turn(1, "user", "first?"),
  turn(2, "assistant", "First answer."),
  turn(3, "user", "second?"),
  turn(4, "assistant", "Second answer."),
  turn(5, "user", "third?"),
  turn(6, "assistant", "", {
    type: "error",
    kind: "provider_rate_limited",
    message: "slow down",
  }),
]

const MODEL: ModelSelection = {
  model_type: "text_gen",
  provider: "llamacpp",
  connection_id: null,
  name: "Qwen3-1.7B-Q4_K_M",
  updated_at: "2026-09-05T00:00:00Z",
}

function panel(handlers: {
  onRetry: (assistantId: string) => void
  onCitation?: (chunkId: number) => void
  dictation?: Dictation
  threadId?: number
}) {
  const threadId = handlers.threadId ?? THREAD.id
  const props: ComponentProps<typeof ThreadPanel> = {
    live: {
      threadId,
      persistedMessages: HISTORY,
      adapters: handlers.dictation
        ? { dictation: handlers.dictation }
        : undefined,
      isSendDisabled: false,
      onNew: async () => undefined,
      onCancel: async () => undefined,
    },
    thread: { ...THREAD, id: threadId },
    view: { status: "active", threadId },
    model: handlers.dictation ? MODEL : null,
    dictation: handlers.dictation,
    isLoading: false,
    isRunning: false,
    animateTitle: false,
    providerAvailable: true,
    sourceCount: 0,
    onCitation: handlers.onCitation ?? (() => undefined),
    onModelSetup: () => undefined,
    onModelSelected: () => undefined,
    onRetry: handlers.onRetry,
    onNewChat: () => undefined,
    onTitleAnimationComplete: () => undefined,
    autoNamingThreadId: null,
    onRename: async () => true,
    onDelete: async () => undefined,
  }
  return <ThreadPanel {...props} />
}

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json([]))
  )
  // jsdom lays nothing out; the viewport scrolls to the newest message.
  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("thread panel", () => {
  it("re-renders no reply for new handlers, and calls the newest", async () => {
    const first = vi.fn()
    const { rerender } = render(panel({ onRetry: first }))
    await screen.findByText("Second answer.")
    const replies = vi.mocked(AssistantMessage)
    replies.mockClear()

    const latest = vi.fn()
    rerender(panel({ onRetry: latest, onCitation: () => undefined }))
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))

    expect(replies).not.toHaveBeenCalled()
    expect(latest).toHaveBeenCalledWith("6")
    expect(first).not.toHaveBeenCalled()
  })

  it("cancels voice input on a thread switch, so nothing lands in the next thread", async () => {
    const api = fakeDictationApi()
    const late = held(() => Response.json(said("For the first thread.")))
    api.answer(late.answer)
    vi.mocked(fetch).mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) =>
        (await api.handle(String(input), init)) ?? Response.json([])
    )
    const mic = fakeMicrophone()
    const dictation = createDictation({ openMicrophone: mic.open })
    const user = userEvent.setup()
    const { rerender } = render(panel({ onRetry: () => undefined, dictation }))

    await user.click(
      await screen.findByRole("button", { name: "Start voice input" })
    )
    await waitFor(() => expect(mic.state.open).toBe(true))
    act(() => mic.say())
    await waitFor(() => expect(api.phrases).toHaveLength(1))
    rerender(panel({ onRetry: () => undefined, dictation, threadId: 2 }))

    expect(mic.state.open).toBe(false)
    late.release()
    await waitFor(() =>
      expect(api.calls).toContain("DELETE /llm/transcription/dictations/d1")
    )
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(
      screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
        .value
    ).toBe("")
    expect(dictation.getView().phase).toBe("idle")
  })
})
