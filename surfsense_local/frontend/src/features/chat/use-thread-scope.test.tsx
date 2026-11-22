import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SourceScope } from "@/features/sources/tree/scope-state"

import type { ChatThread } from "./api"
import type { NumberedEvent } from "./sse"
import { beginRun, pump, resetChatRuns } from "./runs/run-store"
import type { ConversationView } from "./use-chat-runtime"
import { threadOpenedForNewChat, useThreadScope } from "./use-thread-scope"

vi.mock("./api", () => ({ storeThreadScope: vi.fn() }))
vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

const { storeThreadScope } = await import("./api")

const stored: SourceScope = {
  all: true,
  folder_ids: [],
  excluded_folder_ids: [2],
  document_ids: [],
  excluded_document_ids: [],
}
const without = (ids: number[]): SourceScope => ({
  all: true,
  folder_ids: [],
  excluded_folder_ids: [],
  document_ids: [],
  excluded_document_ids: ids,
})

afterEach(() => {
  localStorage.clear()
  resetChatRuns()
  vi.mocked(storeThreadScope).mockReset()
})

/** A reply that ends as soon as it is followed. */
async function* noFrames(): AsyncGenerator<NumberedEvent> {}

describe("storing a thread's ticks", () => {
  const thread: ChatThread = {
    id: 10,
    workspace_id: 1,
    title: "Research only",
    uses_agent: false,
    source_scope: null,
    created_at: "2026-09-05T00:00:00Z",
    updated_at: "2026-09-05T00:00:00Z",
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )

  it("runs one store after another per thread, so an older one cannot land last", async () => {
    const settle: Array<() => void> = []
    vi.mocked(storeThreadScope).mockImplementation(
      () =>
        new Promise((resolve) => {
          settle.push(() =>
            resolve({
              source_scope: stored,
              counts: { ready: 0, indexing: 0, failed: 0, removed: 0 },
            })
          )
        })
    )
    const setSourceScope = vi.fn()
    const { rerender } = renderHook(
      (props: { scope: SourceScope; edits: number }) =>
        useThreadScope({
          workspaceId: 1,
          view: { status: "active", threadId: 10 },
          activeThread: thread,
          sourceScope: props.scope,
          scopeEdits: props.edits,
          setSourceScope,
          keepScopeForChat: vi.fn(),
          rememberShownScope: vi.fn(),
          showRememberedScope: vi.fn(),
        }),
      { wrapper, initialProps: { scope: without([]), edits: 0 } }
    )
    // Opening the thread put its ticks on screen; a store is a microtask away.
    expect(setSourceScope).toHaveBeenCalledTimes(1)
    // Two ticks in a row: the second store waits for the first to settle.
    rerender({ scope: without([20]), edits: 1 })
    rerender({ scope: without([20, 21]), edits: 2 })
    await act(async () => {})
    expect(vi.mocked(storeThreadScope).mock.calls).toEqual([
      [10, without([20])],
    ])
    await act(async () => {
      settle[0]?.()
    })
    expect(vi.mocked(storeThreadScope).mock.calls).toEqual([
      [10, without([20])],
      [10, without([20, 21])],
    ])
    expect(setSourceScope).toHaveBeenCalledTimes(1)
    // The thread's stores outlive the page: leave none pending behind.
    await act(async () => {
      settle[1]?.()
    })
  })

  it("holds a tick made while the reply runs, and stores it once the reply ends even after the page is gone", async () => {
    vi.mocked(storeThreadScope).mockResolvedValue({
      source_scope: stored,
      counts: { ready: 0, indexing: 0, failed: 0, removed: 0 },
    })
    beginRun(10, { workspaceId: 1 })
    const { rerender, unmount } = renderHook(
      (props: { scope: SourceScope; edits: number }) =>
        useThreadScope({
          workspaceId: 1,
          view: { status: "active", threadId: 10 },
          activeThread: thread,
          sourceScope: props.scope,
          scopeEdits: props.edits,
          setSourceScope: vi.fn(),
          keepScopeForChat: vi.fn(),
          rememberShownScope: vi.fn(),
          showRememberedScope: vi.fn(),
        }),
      { wrapper, initialProps: { scope: without([]), edits: 0 } }
    )
    rerender({ scope: without([20]), edits: 1 })
    await act(async () => {})
    expect(storeThreadScope).not.toHaveBeenCalled()
    // The user leaves the page while the reply is still coming in.
    unmount()
    await act(async () => {
      await pump(10, noFrames())
    })
    expect(vi.mocked(storeThreadScope).mock.calls).toEqual([
      [10, without([20])],
    ])
  })
})

describe("a new chat's ticks", () => {
  const existing: ChatThread = {
    id: 10,
    workspace_id: 1,
    title: "Research only",
    uses_agent: false,
    source_scope: stored,
    created_at: "2026-09-05T00:00:00Z",
    updated_at: "2026-09-05T00:00:00Z",
  }
  // The fallback: an entry without a scope, which the API never sends.
  const opened: ChatThread = {
    id: 11,
    workspace_id: 1,
    title: "New chat",
    uses_agent: false,
    created_at: "2026-09-05T00:00:00Z",
    updated_at: "2026-09-05T00:00:00Z",
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
  type Props = {
    view: ConversationView
    activeThread: ChatThread | null
    scope: SourceScope
    edits: number
  }
  function render(initialProps: Props) {
    const callbacks = {
      setSourceScope: vi.fn(),
      keepScopeForChat: vi.fn(),
      rememberShownScope: vi.fn(),
      showRememberedScope: vi.fn(),
    }
    const hook = renderHook(
      (props: Props) =>
        useThreadScope({
          workspaceId: 1,
          view: props.view,
          activeThread: props.activeThread,
          sourceScope: props.scope,
          scopeEdits: props.edits,
          ...callbacks,
        }),
      { wrapper, initialProps }
    )
    return { ...hook, ...callbacks }
  }

  it("shows what the workspace remembers, and leaves its ticks to the workspace", async () => {
    const { rerender, showRememberedScope, setSourceScope, keepScopeForChat } =
      render({
        view: { status: "new" },
        activeThread: null,
        scope: without([]),
        edits: 0,
      })
    expect(showRememberedScope).toHaveBeenCalledTimes(1)
    rerender({
      view: { status: "new" },
      activeThread: null,
      scope: without([20]),
      edits: 1,
    })
    await act(async () => {})
    expect(storeThreadScope).not.toHaveBeenCalled()
    expect(setSourceScope).not.toHaveBeenCalled()
    expect(keepScopeForChat).not.toHaveBeenCalled()
    expect(showRememberedScope).toHaveBeenCalledTimes(1)
  })

  it("stores a tick made while its thread was opening on that thread alone", async () => {
    vi.mocked(storeThreadScope).mockResolvedValue({
      source_scope: stored,
      counts: { ready: 0, indexing: 0, failed: 0, removed: 0 },
    })
    const { rerender, keepScopeForChat, rememberShownScope, setSourceScope } =
      render({
        view: { status: "new" },
        activeThread: null,
        scope: without([]),
        edits: 0,
      })
    rerender({
      view: { status: "creating" },
      activeThread: null,
      scope: without([]),
      edits: 0,
    })
    // From here the ticks on screen are the thread's, not the workspace's.
    expect(keepScopeForChat).toHaveBeenCalled()
    rerender({
      view: { status: "creating" },
      activeThread: null,
      scope: without([20]),
      edits: 1,
    })
    await act(async () => {})
    expect(storeThreadScope).not.toHaveBeenCalled()

    threadOpenedForNewChat(11)
    rerender({
      view: { status: "active", threadId: 11 },
      activeThread: opened,
      scope: without([20]),
      edits: 1,
    })
    await act(async () => {})
    expect(vi.mocked(storeThreadScope).mock.calls).toEqual([
      [11, without([20])],
    ])
    expect(rememberShownScope).not.toHaveBeenCalled()
    expect(setSourceScope).not.toHaveBeenCalled()
  })

  it("keeps a tick made while its thread was opening off another chat opened first", async () => {
    const { rerender, setSourceScope, rememberShownScope } = render({
      view: { status: "new" },
      activeThread: null,
      scope: without([]),
      edits: 0,
    })
    rerender({
      view: { status: "creating" },
      activeThread: null,
      scope: without([20]),
      edits: 1,
    })
    // The user opens another chat before the new one's thread exists.
    rerender({
      view: { status: "active", threadId: 10 },
      activeThread: existing,
      scope: without([20]),
      edits: 1,
    })
    await act(async () => {})
    expect(storeThreadScope).not.toHaveBeenCalled()
    // The tick goes back to the new chat's ticks before this chat's own show.
    expect(rememberShownScope).toHaveBeenCalledTimes(1)
    expect(setSourceScope).toHaveBeenCalledExactlyOnceWith(stored)
    expect(rememberShownScope.mock.invocationCallOrder[0]).toBeLessThan(
      setSourceScope.mock.invocationCallOrder[0]!
    )

    // A tick in that chat is its own again.
    vi.mocked(storeThreadScope).mockResolvedValue({
      source_scope: stored,
      counts: { ready: 0, indexing: 0, failed: 0, removed: 0 },
    })
    rerender({
      view: { status: "active", threadId: 10 },
      activeThread: existing,
      scope: without([21]),
      edits: 2,
    })
    await act(async () => {})
    expect(vi.mocked(storeThreadScope).mock.calls).toEqual([
      [10, without([21])],
    ])
    expect(rememberShownScope).toHaveBeenCalledTimes(1)
  })

  it("hands a tick back to the new chat when its thread never opened", async () => {
    const { rerender, rememberShownScope, showRememberedScope } = render({
      view: { status: "new" },
      activeThread: null,
      scope: without([]),
      edits: 0,
    })
    rerender({
      view: { status: "creating" },
      activeThread: null,
      scope: without([20]),
      edits: 1,
    })
    // The thread was refused: the question comes back to the new chat.
    rerender({
      view: { status: "new" },
      activeThread: null,
      scope: without([20]),
      edits: 1,
    })
    await act(async () => {})
    expect(rememberShownScope).toHaveBeenCalledTimes(1)
    // The ticks on screen stay: the remembered ones are not read over them.
    expect(showRememberedScope).toHaveBeenCalledTimes(1)
    expect(storeThreadScope).not.toHaveBeenCalled()
  })

  it("leaves a tick made before a chat's entry arrived to that chat", async () => {
    vi.mocked(storeThreadScope).mockResolvedValue({
      source_scope: stored,
      counts: { ready: 0, indexing: 0, failed: 0, removed: 0 },
    })
    const { rerender, keepScopeForChat, showRememberedScope, setSourceScope } =
      render({
        view: { status: "active", threadId: 10 },
        activeThread: null,
        scope: without([]),
        edits: 0,
      })
    // The chat is open but not listed yet: the workspace stops remembering.
    expect(keepScopeForChat).toHaveBeenCalled()
    expect(showRememberedScope).not.toHaveBeenCalled()
    rerender({
      view: { status: "active", threadId: 10 },
      activeThread: null,
      scope: without([20]),
      edits: 1,
    })
    rerender({
      view: { status: "active", threadId: 10 },
      activeThread: existing,
      scope: without([20]),
      edits: 1,
    })
    await act(async () => {})
    expect(vi.mocked(storeThreadScope).mock.calls).toEqual([
      [10, without([20])],
    ])
    expect(setSourceScope).not.toHaveBeenCalled()
  })
})
