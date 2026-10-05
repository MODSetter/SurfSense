import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"

import { ChatsDialog } from "./chats-dialog"

function baseProps() {
  return {
    open: true,
    onOpenChange: vi.fn(),
    threads: [],
    activeThreadId: null,
    autoNamingThreadId: null,
    animatingTitleThreadId: null,
    isLoading: false,
    onSelect: vi.fn(),
    onNewChat: vi.fn(),
    onRename: vi.fn(async () => true),
    onDelete: vi.fn(async () => undefined),
    onTitleAnimationComplete: vi.fn(),
  }
}

afterEach(cleanup)

describe("ChatsDialog", () => {
  it("shows every chat and an empty state when there are none", () => {
    render(<ChatsDialog {...baseProps()} />)

    expect(screen.getByRole("heading", { name: "Chats" })).toBeTruthy()
    expect(screen.getByText("Start a conversation to see it here")).toBeTruthy()
  })

  it("selects a chat and closes the dialog", async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const onOpenChange = vi.fn()

    render(
      <ChatsDialog
        {...baseProps()}
        onOpenChange={onOpenChange}
        onSelect={onSelect}
        threads={[
          {
            id: 1,
            workspace_id: 1,
            title: "Q3 rollup",
            uses_agent: false,
            created_at: "2026-09-08T00:00:00Z",
            updated_at: "2026-09-08T00:00:00Z",
          },
        ]}
      />
    )

    await user.click(screen.getByRole("button", { name: "Q3 rollup" }))
    expect(onSelect).toHaveBeenCalledWith(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("starts a new chat from the footer and closes the dialog", async () => {
    const user = userEvent.setup()
    const onNewChat = vi.fn()
    const onOpenChange = vi.fn()

    render(
      <ChatsDialog
        {...baseProps()}
        onNewChat={onNewChat}
        onOpenChange={onOpenChange}
      />
    )

    await user.click(screen.getByRole("button", { name: "New chat" }))
    expect(onNewChat).toHaveBeenCalledOnce()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("renames a chat through the row menu", async () => {
    const user = userEvent.setup()
    const onRename = vi.fn(async () => true)

    render(
      <ChatsDialog
        {...baseProps()}
        onRename={onRename}
        threads={[
          {
            id: 1,
            workspace_id: 1,
            title: "Untitled",
            uses_agent: false,
            created_at: "2026-09-08T00:00:00Z",
            updated_at: "2026-09-08T00:00:00Z",
          },
        ]}
      />
    )

    await user.click(
      screen.getByRole("button", { name: "Actions for Untitled" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }))

    const input = screen.getByRole("textbox", { name: "Chat name" })
    await user.clear(input)
    await user.type(input, "Renamed{Enter}")

    expect(onRename).toHaveBeenCalledWith(1, "Renamed")
  })

  it("deletes a chat through the row menu", async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn(async () => undefined)

    render(
      <ChatsDialog
        {...baseProps()}
        onDelete={onDelete}
        threads={[
          {
            id: 1,
            workspace_id: 1,
            title: "Untitled",
            uses_agent: false,
            created_at: "2026-09-08T00:00:00Z",
            updated_at: "2026-09-08T00:00:00Z",
          },
        ]}
      />
    )

    await user.click(
      screen.getByRole("button", { name: "Actions for Untitled" })
    )
    await user.click(
      await screen.findByRole("menuitem", { name: "Delete chat" })
    )

    expect(onDelete).toHaveBeenCalledWith(1)
  })

  it("clears the search from its own button and keeps focus in the box", async () => {
    const user = userEvent.setup()
    render(<ChatsDialog {...baseProps()} />)
    const search = screen.getByRole<HTMLInputElement>("searchbox", {
      name: "Search chats",
    })
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()

    await user.type(search, "notes")
    await user.click(screen.getByRole("button", { name: "Clear search" }))

    expect(search.value).toBe("")
    expect(document.activeElement).toBe(search)
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()
  })
})

describe("ChatsDialog, with replies running", () => {
  const threads = [1, 2, 3, 4].map((id) => ({
    id,
    workspace_id: 1,
    title: `Thread ${id}`,
    uses_agent: false,
    created_at: "2026-10-05T00:00:00Z",
    updated_at: "2026-10-05T00:00:00Z",
  }))

  it("says which threads are writing, waiting, or have a reply not yet read", () => {
    render(
      <ChatsDialog
        {...baseProps()}
        threads={threads}
        runStates={{
          1: { state: "running" },
          2: { state: "queued", position: 1 },
        }}
        unreadThreadIds={[3]}
      />
    )

    const row = (name: string) =>
      screen.getByRole("button", { name }).closest("div") as HTMLElement
    expect(row("Thread 1").textContent).toContain("Writing…")
    expect(row("Thread 2").textContent).toContain("Waiting")
    expect(row("Thread 3").textContent).toContain("New reply")
    expect(row("Thread 4").textContent).not.toMatch(/Writing|Waiting|New reply/)
  })
})
