import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SourceScope } from "@/features/sources/tree/scope-state"

import type { ChatThread } from "./api"
import {
  clearDraftScope,
  readDraftScope,
  useThreadScope,
} from "./use-thread-scope"

vi.mock("./api", () => ({ storeThreadScope: vi.fn() }))
vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

const { storeThreadScope } = await import("./api")

const key = "surfsense:draft-scope:1:v1"
const draft: SourceScope = {
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
  vi.mocked(storeThreadScope).mockReset()
})

describe("a new chat's draft", () => {
  it("reads only a whole draft back", () => {
    expect(readDraftScope(1)).toBeNull()
    localStorage.setItem(key, JSON.stringify(draft))
    expect(readDraftScope(1)).toEqual(draft)
    localStorage.setItem(key, JSON.stringify({ all: true, folder_ids: ["2"] }))
    expect(readDraftScope(1)).toBeNull()
    localStorage.setItem(key, "not json")
    expect(readDraftScope(1)).toBeNull()
  })

  it("is spent once its thread is opened", () => {
    localStorage.setItem(key, JSON.stringify(draft))
    clearDraftScope(1)
    expect(readDraftScope(1)).toBeNull()
  })
})

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
              source_scope: draft,
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
  })
})
