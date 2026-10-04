import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"
import { DashboardPage } from "@/features/dashboard/dashboard-page"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

import { IMAGE_ACCEPT } from "./image-attachments"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}
const thread = { ...workspace, id: 10, workspace_id: 1, title: "Chart" }
const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

function selection(readsImages: boolean): ModelSelection {
  return {
    model_type: "text_gen",
    provider: "llamacpp",
    connection_id: null,
    name: "gemma-3-4b",
    updated_at: "2026-09-05T00:00:00Z",
    reads_images: readsImages,
  }
}

/** A backend with one thread whose history is `stored`, recording what is sent. */
function backend(stored: unknown[] = []) {
  const sent: Record<string, unknown>[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (path.startsWith("/workspaces/1/documents")) return Response.json([])
      if (path === "/workspaces/1/chat/threads") return Response.json([thread])
      if (path === "/chat/threads/10/messages" && init?.method === "POST") {
        sent.push(JSON.parse(String(init.body)))
        return new Response(
          'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"completed","assistant_completed_at":"2026-09-05T00:00:01Z"}\n\ndata: [DONE]\n\n',
          { headers: { "Content-Type": "text/event-stream" } }
        )
      }
      if (path === "/chat/threads/10/messages") return Response.json(stored)
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return sent
}

function renderChat(readsImages: boolean) {
  localStorage.setItem("surfsense:last-thread:1:v1", "10")
  render(
    <TooltipProvider>
      <DashboardPage
        initialProviderAvailable={true}
        selection={selection(readsImages)}
        initialWorkspaces={[workspace]}
        onModelSelected={vi.fn()}
      />
    </TooltipProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  for (const method of ["scrollTo", "scrollIntoView"]) {
    Object.defineProperty(HTMLElement.prototype, method, {
      configurable: true,
      value: vi.fn(),
    })
  }
  vi.stubGlobal("surfsense", { apiUrl: "", platform: "darwin" })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("images in chat", () => {
  it("explains why attach is off while the model cannot read images", async () => {
    backend()
    const user = userEvent.setup()
    renderChat(false)

    await user.click(
      await screen.findByRole("button", {
        name: "Add images, sources, and more",
      })
    )
    const attach = await screen.findByRole("menuitem", {
      name: /^Attach images/,
    })
    expect(attach.getAttribute("aria-disabled")).toBe("true")
    await user.hover(attach)
    await waitFor(() =>
      expect(screen.getAllByText("This model can’t read images")).toHaveLength(
        2
      )
    )
  })

  it("opens a picker for image formats only while the model reads images", async () => {
    backend()
    const user = userEvent.setup()
    const opened: HTMLInputElement[] = []
    vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(function (
      this: HTMLInputElement
    ) {
      opened.push(this)
    })
    renderChat(true)

    await user.click(
      await screen.findByRole("button", {
        name: "Add images, sources, and more",
      })
    )
    const attach = await screen.findByRole("menuitem", {
      name: /^Attach images/,
    })
    expect(attach.getAttribute("aria-disabled")).toBeNull()
    await user.hover(attach)
    await waitFor(() =>
      expect(screen.getAllByText("Add images to this message")).toHaveLength(2)
    )
    await user.click(attach)

    await waitFor(() => expect(opened).toHaveLength(1))
    expect(opened[0]?.type).toBe("file")
    expect(opened[0]?.accept).toBe(IMAGE_ACCEPT)
    expect(opened[0]?.multiple).toBe(true)
  })

  it("sends a pasted image with the question, and it can be removed first", async () => {
    const sent = backend()
    const user = userEvent.setup()
    renderChat(true)
    const input = await screen.findByRole("textbox", { name: "Message" })

    const paste = () =>
      fireEvent.paste(input, {
        clipboardData: {
          files: [new File([PNG], "chart.png", { type: "image/png" })],
        },
      })
    paste()
    await user.click(
      await screen.findByRole("button", { name: "Remove image" })
    )
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Remove image" })).toBeNull()
    )
    paste()
    await screen.findByRole("button", { name: "Remove image" })
    await user.type(input, "what does it show?{Enter}")

    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0]).toMatchObject({
      text: "what does it show?",
      images: [{ mime: "image/png", data: btoa(String.fromCharCode(...PNG)) }],
    })
  })

  it("sends a text turn exactly as before", async () => {
    const sent = backend()
    const user = userEvent.setup()
    renderChat(true)
    const input = await screen.findByRole("textbox", { name: "Message" })

    await user.type(input, "hello{Enter}")

    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0]).not.toHaveProperty("images")
  })

  it("shows a stored turn's images from the image route", async () => {
    backend([
      {
        id: 100,
        role: "user",
        content: {
          text: "what is this?",
          images: [
            { key: "k", mime: "image/jpeg", size_bytes: 3, sha256: "s" },
          ],
        },
        created_at: "2026-09-05T00:00:00Z",
        completed_at: null,
      },
    ])
    renderChat(false)

    const image = await screen.findByRole("img", { name: "Attached image" })

    expect(image.getAttribute("src")).toBe(
      "/chat/threads/10/messages/100/images/0"
    )
  })
})
