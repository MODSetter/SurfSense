import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { AppDialogs } from "@/components/ui/app-dialog-slot"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { requestVoid } from "@/lib/api"
import { render } from "@/test-utils"

import { askEgress } from "./ask-egress"
import { EgressPrompt } from "./egress-prompt"

const REFUSED = {
  detail: {
    code: "egress_disabled",
    message: "off",
    destination: "host:api.provider.example",
    host: "api.provider.example",
  },
}

function stubApi() {
  const calls: string[] = []
  let allowed = false
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      calls.push(`${init?.method ?? "GET"} ${path}`)
      if (path.startsWith("/egress/")) {
        allowed = true
        return Response.json({})
      }
      return allowed
        ? Response.json({})
        : Response.json(REFUSED, { status: 403 })
    })
  )
  return calls
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("egress prompt", () => {
  it("asks about the host and, once allowed, lets the call through", async () => {
    const calls = stubApi()
    const user = userEvent.setup()
    render(<EgressPrompt />)

    const pending = requestVoid("/chat/threads/1/messages", { method: "POST" })
    await screen.findByRole("alertdialog", {
      name: "Allow sending data to api.provider.example?",
    })
    await user.click(screen.getByRole("button", { name: "Allow" }))

    await expect(pending).resolves.toBeUndefined()
    expect(calls).toEqual([
      "POST /chat/threads/1/messages",
      "PUT /egress/host:api.provider.example",
      "POST /chat/threads/1/messages",
    ])
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
  })

  it("tells the truth about huggingface.co: typing and names, not documents", async () => {
    // One host for three errands, so one question has to cover all of them
    // without borrowing the copy written for a chat endpoint.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              code: "egress_disabled",
              message: "off",
              destination: "host:huggingface.co",
              host: "huggingface.co",
            },
          },
          { status: 403 }
        )
      )
    )
    render(<EgressPrompt />)

    void requestVoid("/llm/installs", { method: "POST" }).catch(() => {})

    const dialog = await screen.findByRole("alertdialog")
    expect(dialog.textContent).toContain("what you type")
    expect(dialog.textContent).toContain("the model you chose")
    expect(dialog.textContent).not.toContain("excerpts of your documents")
  })

  it("cancelling leaves the call refused", async () => {
    const calls = stubApi()
    const user = userEvent.setup()
    render(<EgressPrompt />)

    const refused = expect(
      requestVoid("/chat/threads/1/messages", { method: "POST" })
    ).rejects.toMatchObject({ code: "egress_disabled" })
    await screen.findByRole("alertdialog")
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    await refused
    expect(calls).toEqual(["POST /chat/threads/1/messages"])
  })

  it("asks about a refused request as the open dialog's nested dialog", async () => {
    stubApi()
    render(
      <AppDialogs dialogs={[EgressPrompt]}>
        <Dialog open>
          <DialogContent>
            <DialogTitle>Connect a server</DialogTitle>
          </DialogContent>
        </Dialog>
      </AppDialogs>
    )

    void requestVoid("/llm/connections", { method: "POST" }).catch(() => {})

    await screen.findByRole("alertdialog")
    expect(screen.getAllByRole("alertdialog")).toHaveLength(1)
    // Base UI steps the parent back only for a dialog rendered inside it.
    await waitFor(() =>
      expect(
        document
          .querySelector('[role="dialog"]')
          ?.hasAttribute("data-nested-dialog-open")
      ).toBe(true)
    )
  })

  it("asks queued questions one after another", async () => {
    const user = userEvent.setup()
    render(<EgressPrompt />)
    const ask = (host: string) =>
      askEgress({
        destination: `host:${host}`,
        host,
        allow: async () => undefined,
      })
    let first: Promise<boolean> = Promise.resolve(true)
    act(() => {
      first = ask("a.example")
      void ask("b.example")
    })

    await screen.findByRole("alertdialog", {
      name: "Allow sending data to a.example?",
    })
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    await expect(first).resolves.toBe(false)
    expect(
      await screen.findByRole("alertdialog", {
        name: "Allow sending data to b.example?",
      })
    ).toBeTruthy()
  })

  it("answers no to a question left open when the prompt goes away", async () => {
    const view = render(<EgressPrompt />)
    let answer: Promise<boolean> = Promise.resolve(true)
    act(() => {
      answer = askEgress({
        destination: "app_updates",
        host: "github.com",
        allow: async () => undefined,
      })
    })
    await screen.findByRole("alertdialog")

    view.unmount()

    await expect(answer).resolves.toBe(false)
  })
})
