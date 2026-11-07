import { describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook } from "@testing-library/react"
import type { ReactNode } from "react"

import type { WorkspaceChange } from "@/features/workspaces/workspace-changes"

import type { ChatMessage } from "./api"
import { chatKeys } from "./query-keys"
import { useRefreshQueuedVersions } from "./use-refresh-queued-versions"

const change = vi.hoisted(() => ({
  fire: (_change?: WorkspaceChange) => {},
}))

vi.mock("@/features/workspaces/use-workspace-changes", () => ({
  useWorkspaceChanges: (
    _workspaceId: number,
    _kind: string,
    onChange: (change?: WorkspaceChange) => void
  ) => {
    change.fire = onChange
  },
}))

function reply(output: string, artifact: unknown = null): ChatMessage {
  return {
    id: 1,
    role: "assistant",
    content: {
      steps: [
        {
          id: "step",
          tool: "surfsense_make_image",
          status: "completed",
          input: {},
          output,
          artifact,
        },
      ],
    },
  } as unknown as ChatMessage
}

const QUEUED = "Queued artifact 62, version 1: Boat\nStill being made."
const READY = { artifactId: 62, status: "ready" } as unknown as WorkspaceChange

function refreshed(messages: ChatMessage[], event = READY, running = false) {
  const client = new QueryClient()
  client.setQueryData(chatKeys.messages(10), messages)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  renderHook(() => useRefreshQueuedVersions(1, 10, running), { wrapper })
  change.fire(event)
  return client.getQueryState(chatKeys.messages(10))?.isInvalidated
}

describe("a thread waiting on a version", () => {
  it("reads its messages again when an artifact becomes ready", () => {
    expect(refreshed([reply(QUEUED)])).toBe(true)
  })

  it("reads them again when a dropped stream came back", () => {
    expect(refreshed([reply(QUEUED)], undefined)).toBe(true)
  })

  it("waits while the artifact is still being made", () => {
    const making = { status: "processing" } as unknown as WorkspaceChange
    expect(refreshed([reply(QUEUED)], making)).toBe(false)
  })

  it("leaves a thread that has nothing queued", () => {
    const made = reply("Rendered artifact 62, version 1: Boat", { id: 62 })
    expect(refreshed([made])).toBe(false)
  })

  it("leaves a thread with a turn running, which the stream keeps up to date", () => {
    expect(refreshed([reply(QUEUED)], READY, true)).toBe(false)
  })
})
