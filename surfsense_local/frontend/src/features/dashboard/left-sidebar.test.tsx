import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"

import { LeftSidebar, type SidebarNavAction } from "./left-sidebar"

function UnplugIcon(props: { className?: string }) {
  return <svg data-testid="unplug-icon" {...props} />
}

const noop = () => {}

function baseProps() {
  return {
    threads: [],
    activeThreadId: null,
    autoNamingThreadId: null,
    animatingTitleThreadId: null,
    isLoadingThreads: false,
    onNewChat: vi.fn(),
    onSelectThread: vi.fn(),
    onRenameThread: vi.fn(async () => true),
    onDeleteThread: vi.fn(async () => undefined),
    onTitleAnimationComplete: vi.fn(),
    sources: <div data-testid="sources-slot">Sources go here</div>,
  }
}

afterEach(cleanup)

describe("LeftSidebar", () => {
  it("keeps the brand, New chat and Chats rows, with the sources slot below", () => {
    render(<LeftSidebar {...baseProps()} />)

    const brand = screen.getByRole("heading", { name: "SurfSense" })
    expect(brand.className).toContain("font-heading")
    expect(brand.className).toContain("select-none")

    const newChat = screen.getByRole("button", { name: "New chat" })
    expect(newChat.getAttribute("data-variant")).toBe("ghost")
    expect(newChat.closest("header")?.className).toContain("px-3")

    expect(screen.getByRole("button", { name: "Chats" })).toBeTruthy()
    expect(screen.getByTestId("sources-slot")).toBeTruthy()
  })

  it("opens the chats dialog from the Chats row", async () => {
    const user = userEvent.setup()
    render(
      <LeftSidebar
        {...baseProps()}
        threads={[
          {
            id: 1,
            workspace_id: 1,
            title: "Past chat",
            created_at: "2026-09-08T00:00:00Z",
            updated_at: "2026-09-08T00:00:00Z",
          },
        ]}
      />
    )

    expect(screen.queryByRole("dialog")).toBeNull()
    await user.click(screen.getByRole("button", { name: "Chats" }))
    expect(screen.getByRole("dialog")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Past chat" })).toBeTruthy()
  })

  it("renders each extra action the same way as New chat", async () => {
    const onPlugins = vi.fn()
    const user = userEvent.setup()
    const actions: SidebarNavAction[] = [
      {
        key: "plugins",
        label: "Plugins",
        icon: UnplugIcon,
        onClick: onPlugins,
      },
    ]

    render(<LeftSidebar {...baseProps()} actions={actions} />)

    const newChat = screen.getByRole("button", { name: "New chat" })
    const plugins = screen.getByRole("button", { name: "Plugins" })
    expect(plugins.getAttribute("data-variant")).toBe(
      newChat.getAttribute("data-variant")
    )
    expect(plugins.className).toBe(newChat.className)
    expect(plugins.querySelector("[data-testid='unplug-icon']")).toBeTruthy()

    await user.click(plugins)
    expect(onPlugins).toHaveBeenCalledOnce()
  })

  it("shows an action's badge next to its label", () => {
    const actions: SidebarNavAction[] = [
      {
        key: "plugins",
        label: "Plugins",
        icon: UnplugIcon,
        badge: "Coming soon",
        onClick: noop,
      },
    ]

    render(<LeftSidebar {...baseProps()} actions={actions} />)

    const badge = screen.getByText("Coming soon")
    expect(badge.closest('[data-slot="badge"]')).toBeTruthy()
    expect(
      screen.getByRole("button", { name: /^Plugins/ }).contains(badge)
    ).toBe(true)
    expect(
      screen.getByRole("button", { name: "New chat" }).textContent
    ).not.toContain("Coming soon")
  })

  it("pins the footer under the sources slot", () => {
    render(
      <LeftSidebar {...baseProps()} footer={<div>License footer</div>} />
    )

    expect(screen.getByText("License footer")).toBeTruthy()
  })
})
