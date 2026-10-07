import { Profiler, useLayoutEffect } from "react"
import { INTERNAL, useAui } from "@assistant-ui/react"
import { QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, render, waitFor } from "@testing-library/react"
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from "vitest"

import type { ChatMode } from "@/features/models/capability/api"
import { createQueryClient } from "@/lib/query-client"
import { toast } from "sonner"

import type { ChatMessage, ChatThread } from "./api"
import { chatKeys } from "./query-keys"
import { LiveThreadRuntime } from "./live-thread-runtime"
import { liveRun, liveRuns, resetChatRuns } from "./runs/run-store"
import { readUnread } from "./runs/unread-replies"
import type { ChatTurnError } from "./use-chat-runtime"
import { useChatRuntime } from "./use-chat-runtime"

const WORKSPACE = 1
const OTHER_WORKSPACE = 2

function thread(
  id: number,
  running = false,
  extra: Partial<ChatThread> = {}
): ChatThread & { running: boolean } {
  return {
    id,
    workspace_id: WORKSPACE,
    title: `Thread ${id}`,
    uses_agent: false,
    created_at: "2026-10-05T00:00:00Z",
    updated_at: "2026-10-05T00:00:00Z",
    running,
    ...extra,
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
    this.frames([payload])
  }

  /** Frames that arrive in one network read. */
  frames(payloads: Array<object | "[DONE]">) {
    let chunk = ""
    for (const payload of payloads) {
      this.seq += 1
      const data = payload === "[DONE]" ? "[DONE]" : JSON.stringify(payload)
      chunk += `id: ${this.seq}\ndata: ${data}\n\n`
    }
    this.controller.enqueue(new TextEncoder().encode(chunk))
    if (payloads.includes("[DONE]")) this.controller.close()
  }

  /** The window hung up, as an aborted fetch does to its body. */
  hangUp() {
    this.controller.error(new DOMException("aborted", "AbortError"))
  }
}

/** The chat API this window talks to: stored turns, and the streams it opens. */
class FakeApi {
  threads: Array<ChatThread & { running: boolean }> = [thread(1), thread(2)]
  // The other workspace's own thread, for a switch of workspace.
  otherThreads = [thread(3, false, { workspace_id: OTHER_WORKSPACE })]
  messages: Record<number, ChatMessage[]> = { 1: [], 2: [], 3: [] }
  // Answers to the next reads of a thread's turns, before `messages` again.
  nextReads: Record<number, ChatMessage[][]> = {}
  // Reads of a thread's turns that wait, as a slow API answers them.
  private held: Record<number, Promise<void>> = {}
  sends: Array<{ threadId: number; body: Record<string, unknown> }> = []
  // Each new chat's request, and a refusal to answer it with instead.
  creates: Array<Record<string, unknown>> = []
  refuseCreate: { status: number; code: string } | null = null
  sendStreams: Stream[] = []
  stops: number[] = []
  follows: number[] = []

  fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://api")
    const method = (init?.method ?? "GET").toUpperCase()
    const path = url.pathname
    let match: RegExpMatchArray | null
    if (
      path === `/workspaces/${OTHER_WORKSPACE}/chat/threads` &&
      method === "GET"
    ) {
      return Response.json(this.otherThreads)
    }
    if (path === `/workspaces/${WORKSPACE}/chat/threads` && method === "GET") {
      return Response.json(this.threads)
    }
    if (path === `/workspaces/${WORKSPACE}/chat/threads`) {
      this.creates.push(JSON.parse(String(init?.body)))
      if (this.refuseCreate) {
        const { status, code } = this.refuseCreate
        return Response.json(
          { detail: { code, message: "refused" } },
          { status }
        )
      }
      const created = thread(this.threads.length + 1, false, {
        title: "New chat",
      })
      this.threads = [created, ...this.threads]
      this.messages[created.id] = []
      return Response.json(created)
    }
    if ((match = path.match(/^\/chat\/threads\/(\d+)\/messages$/))) {
      const threadId = Number(match[1])
      if (method === "GET") {
        await this.held[threadId]
        return Response.json(
          this.nextReads[threadId]?.shift() ?? this.messages[threadId] ?? []
        )
      }
      const stream = new Stream()
      this.sends.push({ threadId, body: JSON.parse(String(init?.body)) })
      this.sendStreams.push(stream)
      init?.signal?.addEventListener("abort", () => stream.hangUp())
      return new Response(stream.body, {
        headers: { "Content-Type": "text/event-stream" },
      })
    }
    if ((match = path.match(/^\/chat\/threads\/(\d+)\/run\/stop$/))) {
      this.stops.push(Number(match[1]))
      return new Response(null, { status: 204 })
    }
    if ((match = path.match(/^\/chat\/threads\/(\d+)\/run$/))) {
      this.follows.push(Number(match[1]))
      return new Response(null, { status: 404 })
    }
    if (/^\/workspaces\/\d+\/events/.test(path)) {
      return new Response(new ReadableStream())
    }
    return new Response(null, { status: 404 })
  })

  /** Holds every read of a thread's turns until the returned call. */
  holdReads(threadId: number): () => void {
    let release = () => {}
    this.held[threadId] = new Promise((resolve) => {
      release = () => {
        delete this.held[threadId]
        resolve()
      }
    })
    return release
  }
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

type Rendered = ReturnType<typeof useChatRuntime> & {
  // The open thread as its runtime holds it, as the panel reads it.
  thread: ReturnType<ReturnType<typeof useAui>["thread"]>
}

/**
 * The hook as the page uses it, its runtime from LiveThreadRuntime as the
 * thread panel builds it. Counts the renders of the hook's page and of the
 * runtime's subtree apart.
 */
function renderRuntime({
  readsImages = false,
  newChatMode = null as ChatMode | null,
  workspaceId = WORKSPACE,
  // The app's one client, kept across a switch of workspace.
  client = createQueryClient(),
} = {}) {
  const result = { current: undefined as unknown as Rendered }
  const renders = { page: 0, thread: 0 }

  function Probe({ chat }: { chat: ReturnType<typeof useChatRuntime> }) {
    const aui = useAui()
    useLayoutEffect(() => {
      result.current = { ...chat, thread: aui.thread() }
    })
    return null
  }

  function Page() {
    const chat = useChatRuntime({
      workspaceId,
      canSend: true,
      selectedDocumentIds: [],
      selectedSourceTitles: [],
      readsImages,
      canSkipThinking: false,
      newChatMode,
      onModelRequired: vi.fn(),
    })
    renders.page += 1
    return (
      <Profiler id="thread" onRender={() => (renders.thread += 1)}>
        <LiveThreadRuntime {...chat.liveThread}>
          <Probe chat={chat} />
        </LiveThreadRuntime>
      </Profiler>
    )
  }

  render(
    <QueryClientProvider client={client}>
      <Page />
    </QueryClientProvider>
  )
  return { result, renders }
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

function assistantText(result: ReturnType<typeof renderRuntime>["result"]) {
  return result.current.thread
    .getState()
    .messages.filter((m) => m.role === "assistant")
    .map((m) =>
      m.content.map((part) => (part.type === "text" ? part.text : "")).join("")
    )
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
    result.current.thread.append({
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
      expect(assistantText(result)).toEqual(["Revenue climbed."])
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

  it("marks a reply unread in its own workspace when it ends in another", async () => {
    const first = renderRuntime()
    await openThread(first.result, 1)
    sendIn(first.result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() =>
      reply.frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
    )
    // The rail opens the other workspace, whose page mounts in its place.
    cleanup()
    const { result } = renderRuntime({ workspaceId: OTHER_WORKSPACE })
    await waitFor(() => expect(result.current.threads).toHaveLength(1))

    api.messages[1] = [
      stored(11, "user", "How did revenue move?"),
      stored(12, "assistant", "Revenue climbed."),
    ]
    act(() =>
      reply.frames([{ type: "delta", text: "Revenue climbed." }, "[DONE]"])
    )
    await waitFor(() => expect(liveRuns()).toEqual([]))

    expect(readUnread(WORKSPACE)).toEqual([1])
    expect(readUnread(OTHER_WORKSPACE)).toEqual([])
    expect(result.current.unreadThreadIds).toEqual([])
  })

  it("names a thread in its own workspace's list when another is open", async () => {
    const client = createQueryClient()
    const first = renderRuntime({ client })
    await openThread(first.result, 1)
    sendIn(first.result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() =>
      reply.frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
    )
    cleanup()
    const { result } = renderRuntime({ client, workspaceId: OTHER_WORKSPACE })
    await waitFor(() => expect(result.current.threads).toHaveLength(1))

    act(() =>
      reply.frame({ type: "thread-title-update", title: "Revenue by quarter" })
    )
    const titles = () =>
      client
        .getQueryData<ChatThread[]>(chatKeys.threads(WORKSPACE))
        ?.map((listed) => listed.title)

    await waitFor(() =>
      expect(titles()).toEqual(["Revenue by quarter", "Thread 2"])
    )
    api.messages[1] = [
      stored(11, "user", "How did revenue move?"),
      stored(12, "assistant", "Revenue climbed."),
    ]
    act(() =>
      reply.frames([{ type: "delta", text: "Revenue climbed." }, "[DONE]"])
    )
    await waitFor(() => expect(liveRuns()).toEqual([]))
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
      result.current.thread.cancelRun()
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
      const states = result.current.thread.getState().messages
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

  it("keeps an agent turn arriving while another thread is open", async () => {
    api.threads = [thread(1, false, { uses_agent: true }), thread(2)]
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "List the reports")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() => {
      reply.frame({
        type: "accepted",
        user_message_id: "msg_u",
        assistant_message_id: "msg_u:reply",
        user_created_at: "2026-10-05T00:00:00Z",
      })
      reply.frame({ type: "delta", text: "Two " })
    })

    await openThread(result, 2)
    act(() => reply.frame({ type: "delta", text: "reports." }))
    await openThread(result, 1)

    await waitFor(() => expect(assistantText(result)).toEqual(["Two reports."]))
    expect(result.current.isRunning).toBe(true)
  })

  it("asks the API to stop an agent turn instead of hanging up", async () => {
    api.threads = [thread(1, false, { uses_agent: true }), thread(2)]
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "List the reports")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    act(() =>
      api.sendStreams[0].frame({
        type: "accepted",
        user_message_id: "msg_u",
        assistant_message_id: "msg_u:reply",
        user_created_at: "2026-10-05T00:00:00Z",
      })
    )

    await act(async () => {
      result.current.thread.cancelRun()
    })

    await waitFor(() => expect(api.stops).toEqual([1]))
  })

  it("follows an agent turn the list says is running", async () => {
    api.threads = [thread(1, true, { uses_agent: true }), thread(2)]
    const { result } = renderRuntime()

    await openThread(result, 1)

    await waitFor(() => expect(api.follows).toContain(1))
  })

  it("says where each reply stands from the thread list alone", async () => {
    api.threads = [
      thread(1, true, {
        run_state: { state: "needs-approval", position: null },
      }),
      thread(2, true, { run_state: { state: "queued", position: 1 } }),
    ]
    const { result } = renderRuntime()

    await waitFor(() =>
      expect(result.current.runStates).toEqual({
        1: { state: "needs-approval" },
        2: { state: "queued", position: 1 },
      })
    )
  })

  it("asks an agent's pending approval again on returning to its thread", async () => {
    api.threads = [thread(1, false, { uses_agent: true }), thread(2)]
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "List the reports")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() =>
      reply.frame({
        type: "accepted",
        user_message_id: "msg_u",
        assistant_message_id: "msg_u:reply",
        user_created_at: "2026-10-05T00:00:00Z",
      })
    )

    await openThread(result, 2)
    act(() =>
      reply.frame({
        type: "permission-request",
        id: "per_1",
        permission: "doom_loop",
        patterns: [],
        command: null,
      })
    )
    expect(result.current.approvals).toEqual([])
    await openThread(result, 1)

    await waitFor(() =>
      expect(result.current.approvals.map((a) => a.id)).toEqual(["per_1"])
    )
  })

  it("drops a reply that ended elsewhere once a second read holds it", async () => {
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() =>
      reply.frame({
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-10-05T00:00:00Z",
      })
    )
    await openThread(result, 2)

    // The first read after the end lags the store; the next one holds it.
    api.messages[1] = [
      stored(11, "user", "How did revenue move?"),
      stored(12, "assistant", "Revenue climbed."),
    ]
    api.nextReads[1] = [[]]
    act(() =>
      reply.frames([{ type: "delta", text: "Revenue climbed." }, "[DONE]"])
    )

    await waitFor(() => expect(liveRuns()).toEqual([]))
    expect(result.current.activeThreadId).toBe(2)
  })

  it("keeps a Retry pressed while the failed reply's turns are read", async () => {
    const { result } = renderRuntime()
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))

    api.messages[1] = [
      stored(11, "user", "How did revenue move?"),
      stored(12, "assistant", "", {
        type: "error",
        kind: "network",
        message: "unreachable",
      }),
    ]
    // The read after the end answers only once the Retry is on its way.
    const release = api.holdReads(1)
    act(() =>
      api.sendStreams[0].frames([
        {
          type: "accepted",
          user_message_id: 11,
          assistant_message_id: 12,
          user_created_at: "2026-10-05T00:00:00Z",
        },
        {
          type: "error",
          kind: "network",
          message: "unreachable",
          provider: "openai",
        },
        "[DONE]",
      ])
    )
    await waitFor(() => expect(liveRun(1)?.ended).toBe(true))
    act(() => result.current.retry("12"))
    await waitFor(() => expect(api.sends).toHaveLength(2))
    await waitFor(() => expect(result.current.isRunning).toBe(true))

    await act(async () => {
      release()
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
    // The failed run's end found its turns stored, and left the Retry be.
    expect(liveRun(1)).toMatchObject({ ended: false, replaces: [11, 12] })
    expect(result.current.isRunning).toBe(true)
    act(() =>
      api.sendStreams[1].frames([
        {
          type: "accepted",
          user_message_id: 13,
          assistant_message_id: 14,
          user_created_at: "2026-10-05T00:00:02Z",
        },
        { type: "delta", text: "Revenue climbed." },
      ])
    )

    await waitFor(() =>
      expect(assistantText(result)).toEqual(["Revenue climbed."])
    )
    expect(result.current.isRunning).toBe(true)
    expect(liveRun(1)?.ended).toBe(false)
  })

  it("lets go of a sent image's picture once its stored turn shows it", async () => {
    const picture = "data:image/png;base64,aGVsbG8="
    // Every message the runtime holds, on its shown branch or off it: what
    // the thread's export leaves out is still in memory.
    const repositories = new Set<
      InstanceType<typeof INTERNAL.MessageRepository>
    >()
    const repository = INTERNAL.MessageRepository.prototype
    const add = repository.addOrUpdateMessage
    const spy = vi
      .spyOn(repository, "addOrUpdateMessage")
      .mockImplementation(function (this: typeof repository, ...args) {
        repositories.add(this)
        return add.apply(this, args)
      })
    onTestFinished(() => spy.mockRestore())
    const held = () =>
      [...repositories].flatMap((one) =>
        [
          ...(
            one as unknown as {
              messages: Map<string, { current: { id: string } }>
            }
          ).messages.values(),
        ].map((node) => node.current)
      )
    const { result } = renderRuntime({ readsImages: true })
    await openThread(result, 1)
    act(() => {
      result.current.thread.append({
        role: "user",
        content: [{ type: "text", text: "What is this?" }],
        attachments: [
          {
            id: "picked",
            type: "image",
            name: "picked.png",
            contentType: "image/png",
            status: { type: "complete" },
            content: [{ type: "image", image: picture }],
          },
        ],
      })
    })
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    expect(api.sends[0].body).toMatchObject({
      images: [{ mime: "image/png", data: "aGVsbG8=" }],
    })
    await waitFor(() =>
      expect(JSON.stringify(result.current.thread.getState())).toContain(
        picture
      )
    )

    api.messages[1] = [
      {
        ...stored(11, "user", "What is this?"),
        content: {
          text: "What is this?",
          images: [{ key: "k", mime: "image/png", size_bytes: 5, sha256: "s" }],
        },
      },
      stored(12, "assistant", "A greeting."),
    ]
    act(() =>
      api.sendStreams[0].frames([
        {
          type: "accepted",
          user_message_id: 11,
          assistant_message_id: 12,
          user_created_at: "2026-10-05T00:00:00Z",
        },
        { type: "delta", text: "A greeting." },
        { type: "completed", assistant_completed_at: "2026-10-05T00:00:01Z" },
        "[DONE]",
      ])
    )

    await waitFor(() => expect(liveRuns()).toEqual([]))
    await waitFor(() => expect(assistantText(result)).toEqual(["A greeting."]))
    // assistant-ui keeps every message it was given; the placeholder question
    // held the picture after the stored turn took its place.
    expect(held().length).toBeGreaterThan(0)
    expect(
      held()
        .filter((message) => JSON.stringify(message).includes(picture))
        .map((message) => message.id)
    ).toEqual([])
  })
})

describe("while a reply streams", () => {
  async function streaming(
    result: ReturnType<typeof renderRuntime>["result"],
    history: ChatMessage[] = []
  ) {
    api.messages[1] = history
    await openThread(result, 1)
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const reply = api.sendStreams[0]
    act(() =>
      reply.frames([
        {
          type: "accepted",
          user_message_id: 11,
          assistant_message_id: 12,
          user_created_at: "2026-10-05T00:00:00Z",
        },
        { type: "reasoning", text: "Looking at the quarters." },
        { type: "delta", text: "Revenue" },
      ])
    )
    await waitFor(() => expect(assistantText(result).at(-1)).toBe("Revenue"))
    return reply
  }

  const settle = () =>
    act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

  it("renders its tokens in the thread alone, not the page", async () => {
    const { result, renders } = renderRuntime()
    const reply = await streaming(result)
    await settle()
    const page = renders.page

    for (const word of [" climbed", " in", " every", " quarter."]) {
      act(() => reply.frame({ type: "delta", text: word }))
      await settle()
    }

    expect(assistantText(result).at(-1)).toBe(
      "Revenue climbed in every quarter."
    )
    expect(renders.page).toBe(page)
  })

  it("renders the tokens of one network read once", async () => {
    const { result, renders } = renderRuntime()
    const reply = await streaming(result)
    await settle()
    const thread = renders.thread

    act(() =>
      reply.frames(
        Array.from({ length: 20 }, () => ({ type: "delta", text: " more" }))
      )
    )
    await settle()

    expect(assistantText(result).at(-1)).toBe(`Revenue${" more".repeat(20)}`)
    // One render of the runtime, then one of the message it changed.
    expect(renders.thread - thread).toBeLessThanOrEqual(2)
  })

  it("renders nothing for another thread's tokens", async () => {
    const { result, renders } = renderRuntime()
    const reply = await streaming(result)
    await openThread(result, 2)
    await settle()
    const before = { ...renders }

    for (const word of [" climbed", " again."]) {
      act(() => reply.frame({ type: "delta", text: word }))
      await settle()
    }

    expect(renders).toEqual(before)
  })

  it("keeps every other message as it was", async () => {
    const { result } = renderRuntime()
    const reply = await streaming(result, [
      stored(1, "user", "first?"),
      stored(2, "assistant", "First answer."),
    ])
    const [question, answer] = result.current.thread.getState().messages
    const live = result.current.thread.getState().messages.at(-1)!
    const reasoning = live.metadata.custom.reasoning

    act(() => reply.frame({ type: "delta", text: " climbed." }))
    await waitFor(() =>
      expect(assistantText(result).at(-1)).toBe("Revenue climbed.")
    )

    const messages = result.current.thread.getState().messages
    expect(messages[0]).toBe(question)
    expect(messages[1]).toBe(answer)
    // An answer token leaves the trace, so its header has nothing to redraw.
    expect(messages.at(-1)!.metadata.custom.reasoning).toBe(reasoning)
  })

  it("keeps its Retry while tokens arrive", async () => {
    const { result } = renderRuntime()
    const reply = await streaming(result)
    const retry = result.current.retry

    act(() => reply.frame({ type: "delta", text: " climbed." }))
    await settle()

    expect(result.current.retry).toBe(retry)
  })

  it("names a new chat, rendering the page for its name and not its words", async () => {
    const { result, renders } = renderRuntime()
    await waitFor(() => expect(result.current.threads.length).toBe(2))
    sendIn(result, "How did revenue move?")
    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    const created = api.sends[0].threadId
    expect(result.current.autoNamingThreadId).toBe(created)

    const reply = api.sendStreams[0]
    act(() =>
      reply.frames([
        {
          type: "accepted",
          user_message_id: 11,
          assistant_message_id: 12,
          user_created_at: "2026-10-05T00:00:00Z",
        },
        { type: "thread-title-update", title: "Revenue by quarter" },
        { type: "delta", text: "Revenue" },
      ])
    )
    await waitFor(() =>
      expect(result.current.animatingTitleThreadId).toBe(created)
    )
    expect(result.current.autoNamingThreadId).toBeNull()
    expect(result.current.activeThread?.title).toBe("Revenue by quarter")
    await settle()
    const page = renders.page

    for (const word of [" climbed", " again."]) {
      act(() => reply.frame({ type: "delta", text: word }))
      await settle()
    }

    expect(renders.page).toBe(page)
    expect(assistantText(result)).toEqual(["Revenue climbed again."])
  })
})

describe("a new chat's mode", () => {
  it("opens the chat in the mode picked for the model", async () => {
    const { result } = renderRuntime({ newChatMode: "agentic" })
    await waitFor(() => expect(result.current.threads.length).toBe(2))

    sendIn(result, "Draft the board pack")

    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    expect(api.creates).toEqual([{ title: "New chat", mode: "agentic" }])
  })

  it("leaves the mode to the API when the model reports none", async () => {
    const { result } = renderRuntime()
    await waitFor(() => expect(result.current.threads.length).toBe(2))

    sendIn(result, "How did revenue move?")

    await waitFor(() => expect(api.sendStreams).toHaveLength(1))
    expect(api.creates).toEqual([{ title: "New chat" }])
  })

  it("words a refused Agentic chat by its code and sends nothing", async () => {
    const shown = vi.spyOn(toast, "error")
    onTestFinished(() => shown.mockRestore())
    api.refuseCreate = { status: 409, code: "tool_calls_unsupported" }
    const { result } = renderRuntime({ newChatMode: "agentic" })
    await waitFor(() => expect(result.current.threads.length).toBe(2))

    sendIn(result, "Draft the board pack")

    await waitFor(() => expect(shown).toHaveBeenCalled())
    expect(shown.mock.calls[0][0]).toBe(
      "This model can’t use tools, so it can’t run Agentic mode."
    )
    expect(api.sends).toEqual([])
    expect(result.current.conversationView).toEqual({ status: "new" })
  })
})
