import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"

import { ThreadList } from "./thread-list"

afterEach(cleanup)

describe("ThreadList", () => {
  it("keeps long chat titles inside the compact sidebar row", async () => {
    const title = "A chat title long enough to overflow the sidebar width"
    const user = userEvent.setup()

    render(
      <ThreadList
        workspaceName="Workspace"
        threads={[
          {
            id: 1,
            workspace_id: 1,
            title,
            created_at: "2026-09-08T00:00:00Z",
            updated_at: "2026-09-08T00:00:00Z",
          },
        ]}
        activeThreadId={1}
        autoNamingThreadId={null}
        animatingTitleThreadId={null}
        isLoading={false}
        onNewChat={vi.fn()}
        onSelect={vi.fn()}
        onRename={vi.fn(async () => true)}
        onDelete={vi.fn(async () => undefined)}
        onTitleAnimationComplete={vi.fn()}
      />
    )

    const chatButton = screen.getByRole("button", { name: title })
    const actionsButton = screen.getByRole("button", {
      name: `Actions for ${title}`,
    })
    const titleContainer =
      chatButton.querySelector("[aria-hidden=true]")?.parentElement
    const scrollContainer = chatButton
      .closest("aside")
      ?.querySelector(".overflow-x-hidden")

    expect(scrollContainer).toBeTruthy()
    expect(chatButton.parentElement?.className).toContain("w-full")
    expect(chatButton.parentElement?.className).toContain("overflow-hidden")
    expect(chatButton.className).toContain("h-8")
    expect(chatButton.className).toContain("overflow-hidden")
    expect(chatButton.className).toContain("font-normal")
    expect(chatButton.className).not.toContain("font-medium")
    expect(chatButton.className).toContain("text-white")
    expect(chatButton.className).toContain("group-hover:bg-muted")
    expect(chatButton.className).toContain("dark:group-hover:bg-muted/50")
    expect(chatButton.className).toContain("active:!translate-y-0")
    expect(actionsButton.className).toContain("size-6")
    expect(actionsButton.className).toContain("active:translate-y-px")
    expect(titleContainer?.className).toContain("min-w-0")
    expect(titleContainer?.className).not.toContain("truncate")
    expect(titleContainer?.className).toContain("sidebar-row-title-fade")
    expect(titleContainer?.className).toContain(
      "sidebar-row-title-fade-focus-within"
    )

    await user.click(actionsButton)

    expect(chatButton.className.split(" ")).toContain("bg-muted")
    expect(chatButton.className.split(" ")).toContain("dark:bg-muted/50")
    expect(titleContainer?.className).toContain(
      "sidebar-row-title-fade-actions"
    )
  })
})
