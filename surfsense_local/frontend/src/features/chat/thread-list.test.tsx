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
    const brand = screen.getByRole("heading", { name: "SurfSense" })
    const actionsButton = screen.getByRole("button", {
      name: `Actions for ${title}`,
    })
    const titleContainer =
      chatButton.querySelector("[aria-hidden=true]")?.parentElement
    const scrollContainer = chatButton
      .closest("aside")
      ?.querySelector('[data-slot="scroll-shadow-viewport"]')

    expect(scrollContainer).toBeTruthy()
    const newChat = screen.getByRole("button", { name: "New chat" })
    expect(newChat.getAttribute("data-variant")).toBe("ghost")
    expect(newChat.closest("header")?.className).toContain("px-2")
    expect(scrollContainer?.className).toContain("p-2")
    const recents = screen.getByRole("button", { name: "Recents" })
    expect(recents.tagName).toBe("BUTTON")
    expect(recents.className).not.toContain("bg-muted")
    expect(recents.className).toContain("text-muted-foreground")
    expect(recents.className).toContain("hover:text-accent-foreground")
    expect(recents.className).toContain("select-none")
    expect(recents.getAttribute("aria-expanded")).toBe("true")
    expect(recents.querySelector("svg")?.getAttribute("class")).toContain(
      "opacity-0"
    )
    expect(recents.querySelector("svg")?.getAttribute("class")).toContain(
      "group-hover:opacity-100"
    )
    expect(
      chatButton
        .closest("aside")
        ?.querySelector('[data-slot="scroll-shadow-top"]')
    ).toBeTruthy()
    expect(
      chatButton
        .closest("aside")
        ?.querySelector('[data-slot="scroll-shadow-bottom"]')
    ).toBeTruthy()
    expect(brand.className).toContain("font-heading")
    expect(brand.className).toContain("text-lg")
    expect(brand.className).toContain("font-medium")
    expect(brand.className).toContain("text-foreground")
    expect(brand.className).toContain("select-none")
    expect(chatButton.parentElement?.className).toContain("w-full")
    expect(chatButton.parentElement?.className).toContain("overflow-hidden")
    expect(chatButton.className).toContain("h-8")
    expect(chatButton.className).toContain("overflow-hidden")
    expect(chatButton.className).toContain("font-normal")
    expect(chatButton.className).not.toContain("font-medium")
    expect(chatButton.className).toContain("text-foreground")
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

    await user.click(recents)
    expect(recents.getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("button", { name: title })).toBeNull()
  })

  it("shows recents empty copy instead of the icon empty state", () => {
    render(
      <ThreadList
        threads={[]}
        activeThreadId={null}
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

    expect(screen.getByRole("button", { name: "Recents" })).toBeTruthy()
    expect(
      screen.getByText("Start a conversation to see it here")
    ).toBeTruthy()
    expect(screen.queryByText("No chats yet")).toBeNull()
  })
})
