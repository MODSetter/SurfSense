import type { ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { createQueryClient } from "@/lib/query-client"

import type { ChatMessage, ChatThread } from "./api"
import { resetChatRuns } from "./runs/run-store"
import type { ChatTurnError } from "./use-chat-runtime"
import { useChatRuntime } from "./use-chat-runtime"

const WORKSPACE = 1

function thread(
  id: number,
  running = false
): ChatThread & { running: boolean } {
  return {
    id,
    workspace_id: WORKSPACE,
    title: `Thread ${id}`,
    uses_agent: false,
    created_at: "2026-10-05T00:00:00Z",
    updated_at: "2026-10-05T00:00:00Z",
    running,
  }
}

/** A stream the test writes frames into, as the API sends them. */
class Stream {
  private controller!: ReadableStreamDefaultController<Uint8Array>
  private seq = 0
  readonly body = new ReadableStream<Uint8Array>({
    start: (controller) => {
      this.controller = controller
    },
  })

  frame(payload: object | "[DONE]") {
    this.seq += 1
    const data = payload === "[DONE]" ? "[DONE]" : JSON.stringify(payload)
    this.controller.enqueue(
      new TextEncoder().encode(`id: ${this.seq}\ndata: ${data}\n\n`)
    )
    if (payload === "[DONE]") this.controller.close()
  }
}

/** The chat API this window talks to: stored turns, and the streams it opens. */
class FakeApi {
  threads: Array<ChatThread & { running: boolean }> = [thread(1), thread(2)]
  messages: Record<number, ChatMessage[]> = { 1: [], 2: [] }
  sends: Array<{ threadId: number; body: Record<string, unknown> }> = []
  sendStreams: Stream[] = []
  stops: number[] = []

  fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://api")
    const method = (init?.method ?? "GET").toUpperCase()
    const path = url.pathname
    let match: RegExpMatchArray | null
    if (path === `/workspaces/${WORKSPACE}/chat/threads` && method === "GET") {
      return Response.json(this.threads)
    }
    if ((match = path.match(/^\/chat\/threads\/(\d+)\/messages$/))) {
      const threadId = Number(match[1])
      if (method === "GET") return Response.json(this.messages[threadId] ?? [])
      const stream = new Stream()
      this.sends.push({ threadId, body: JSON.parse(String(init?.body)) })
      this.sendStreams.push(stream)
      return new Response(stream.body, {
        headers: { "Content-Type": "text/event-stream" },
      })
    }
    if ((match = path.match(/^\/chat\/threads\/(\d+)\/run\/stop$/))) {
      this.stops.push(Number(match[1]))
      return new Response(null, { status: 204 })
    }
    if (path.match(/^\/chat\/threads\/\d+\/run$/)) {
      return new Response(null, { status: 404 })
    }
    if (path.startsWith(`/workspaces/${WORKSPACE}/events`)) {
      return new Response(new ReadableStream())
    }
    return new Response(null, { status: 404 })
  })
}

let api: FakeApi

beforeEach(() => {
  api = new FakeApi()
  vi.stubGlobal("fetch", api.fetch)
  localStorage.clear()
  resetChatRuns()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderRuntime() {
  const client = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return renderHook(
    () =>
      useChatRuntime({
        workspaceId: WORKSPACE,
        canSend: true,
        selectedDocumentIds: [],
        readsImages: false,
        canSkipThinking: false,
        onModelRequired: vi.fn(),
      }),
    { wrapper }
  )
}

function stored(
  id: number,
  role: "user" | "assistant",
  text: string,
  ending?: object
): ChatMessage {
  return {
    id,
    role,
    content: { text, citations: [], ...(ending ? { ending } : {}) },
    created_at: "2026-10-05T00:00:00Z",
    completed_at: role === "assistant" ? "2026-10-05T00:00:01Z" : null,
  } as ChatMessage
}

function assistantText(messages: ChatMessage[]) {
  return messages
    .filter((m) => m.role === "assistant")
    .map((m) => m.content.text)
}

async function openThread(
  result: ReturnType<typeof renderRuntime>["result"],
  threadId: number
) {
  await waitFor(() => expect(result.current.threads.length).toBe(2))
  act(() => result.current.selectThread(threadId))
  await waitFor(() => expect(result.current.isLoadingMessages).toBe(false))
}

function sendIn(
  result: ReturnType<typeof renderRuntime>["result"],
  text: string
) {
  act(() => {
    result.current.runtime.thread.append({
      role: "user",
      content: [{ type: "text", text }],
    })
  })
}

describe("useChatRuntime", () => {
  it("keeps a reply arriving while another thread is open", async () => {
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() => {
      reply.frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
      reply.frame({ type: "delta", text: "Revenue " })
    })

    await openThread(result, 2)
    act(() => reply.frame({ type: "delta", text: "climbed." }))
    await openThread(result, 1)

    await waitFor(() =>
      expect(assistantText(result.current.messages)).toEqual([
        "Revenue climbed.",
      ])
    )
    expect(result.current.isRunning).toBe(true)
    expect(api.stops).toEqual([])
  })

  it("marks a reply that finished elsewhere unread until its thread is opened", async () => {
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() => {
      reply.frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
    })
    await openThread(result, 2)

    api.messages[1] = [
      stored(11, "user", "How did revenue move?"),
      stored(12, "assistant", "Revenue climbed."),
    ]
    act(() => {
      reply.frame({ type: "delta", text: "Revenue climbed." })
      reply.frame({
        type: "completed",
        assistant_completed_at: "2026-10-05T00:00:01Z",
      })
      reply.frame("[DONE]")
    })
    await waitFor(() => expect(result.current.unreadThreadIds).toEqual([1]))

    await openThread(result, 1)
    expect(result.current.unreadThreadIds).toEqual([])
  })

  it("asks the API to stop instead of hanging up", async () => {
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    act(() =>
      api.sendStreams[0].frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
    )

    await act(async () => {
      result.current.runtime.thread.cancelRun()
    })

    await waitFor(() => expect(api.stops).toEqual([1]))
  })

  it("shows a stored failure with its error, and Retry only on the latest turn", async () => {
    api.messages[1] = [
      stored(1, "user", "first?"),
      stored(2, "assistant", "", {
        type: "error",
        kind: "network",
        message: "unreachable",
      }),
      stored(3, "user", "second?"),
      stored(4, "assistant", "", {
        type: "error",
        kind: "provider_rate_limited",
        message: "slow down",
      }),
    ]
    const { result } = renderRuntime()
    await openThread(result, 1)

    const errors = await waitFor(() => {
      const states = result.current.runtime.thread.getState().messages
      const found = states
        .filter((m) => m.role === "assistant")
        .map((m) =>
          m.status?.type === "incomplete" && m.status.reason === "error"
            ? (m.status.error as ChatTurnError)
            : null
        )
      expect(found.every(Boolean)).toBe(true)
      return found as ChatTurnError[]
    })
    expect(errors.map((e) => [e.kind, e.retryable])).toEqual([
      ["network", false],
      ["provider_rate_limited", true],
    ])

    act(() => result.current.retry("4"))
    await waitFor(() => expect(api.sends).toHaveLength(1))
    expect(api.sends[0].body).toMatchObject({ text: "second?", retry_of: 4 })
  })

  it("shows a reply waiting for the runtime with its place in line", async () => {
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    act(() => {
      api.sendStreams[0].frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
      api.sendStreams[0].frame({
        type: "run-state",
        state: "queued",
        position: 2,
      })
    })

    await waitFor(() =>
      expect(result.current.runStates).toEqual({
        1: { state: "queued", position: 2 },
      })
    )
  })
})
