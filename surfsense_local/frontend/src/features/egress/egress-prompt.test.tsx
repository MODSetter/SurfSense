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
      if (path === "/egress" && init?.method === "PUT") {
        allowed = true
        return Response.json([])
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
  it("asks once about every host a refusal names, and Allow switches on each", async () => {
    const calls: string[] = []
    let allowed = false
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        calls.push(`${init?.method ?? "GET"} ${path}`)
        if (path === "/egress" && init?.method === "PUT") {
          calls[calls.length - 1] +=
            ` ${JSON.parse(String(init.body)).destinations.join(",")}`
          allowed = true
          return Response.json([])
        }
        return allowed
          ? Response.json({})
          : Response.json(
              {
                detail: {
                  code: "egress_disabled",
                  message: "off",
                  destination: "host:api.anthropic.com",
                  host: "api.anthropic.com",
                  hosts: ["api.anthropic.com", "platform.claude.com"],
                  purpose: "claude_plan",
                },
              },
              { status: 403 }
            )
      })
    )
    const user = userEvent.setup()
    render(<EgressPrompt />)

    const pending = requestVoid("/llm/connections/claude", { method: "POST" })
    const prompt = await screen.findByRole("alertdialog", {
      name: "Allow your Claude plan to reach Anthropic?",
    })
    // Each host says what it gets: one the chats, the other only the sign-in.
    expect(prompt.textContent).toContain("api.anthropic.com gets your prompts")
    expect(prompt.textContent).toContain(
      "platform.claude.com only refreshes Claude Code’s sign-in"
    )
    await user.click(screen.getByRole("button", { name: "Allow" }))

    await expect(pending).resolves.toBeUndefined()
    expect(calls).toEqual([
      "POST /llm/connections/claude",
      // One request: Allow switches both on together, or neither.
      "PUT /egress host:api.anthropic.com,host:platform.claude.com",
      "POST /llm/connections/claude",
    ])
  })

  it("names the other hosts a plugin's refusal lists", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              code: "egress_disabled",
              message: "off",
              destination: "host:mcp.notes.example",
              host: "mcp.notes.example",
              hosts: ["mcp.notes.example", "auth.notes.example"],
              purpose: "plugin",
            },
          },
          { status: 403 }
        )
      )
    )
    render(<EgressPrompt />)

    // Handled from the start: Cancel rejects it before the test awaits it.
    const refused = requestVoid("/plugins/custom", { method: "POST" }).catch(
      (error: unknown) => error
    )
    const prompt = await screen.findByRole("alertdialog", {
      name: "Allow connecting to mcp.notes.example?",
    })

    expect(prompt.textContent).toContain(
      "Allowing also lets SurfSense reach auth.notes.example."
    )
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(await refused).toBeInstanceOf(Error)
  })

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
      "PUT /egress",
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

  it("says a plugin's server gets what its tools are sent, not every chat", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              code: "egress_disabled",
              message: "off",
              destination: "host:mcp.notes.example",
              host: "mcp.notes.example",
              purpose: "plugin",
            },
          },
          { status: 403 }
        )
      )
    )
    render(<EgressPrompt />)

    void requestVoid("/plugins/custom", { method: "POST" }).catch(() => {})

    const dialog = await screen.findByRole("alertdialog", {
      name: "Allow connecting to mcp.notes.example?",
    })
    expect(dialog.textContent).toContain("a plugin’s server")
    expect(dialog.textContent).not.toContain("excerpts of your documents")
  })

  it("tells the truth about update checks: version, system and architecture, no ID, GitHub behind", async () => {
    render(<EgressPrompt />)

    void askEgress({
      destination: "app_updates",
      host: "updates.surfsense.com",
      allow: async () => undefined,
    })

    const dialog = await screen.findByRole("alertdialog", {
      name: "Allow SurfSense to check for updates?",
    })
    expect(dialog.textContent).toContain("asks updates.surfsense.com")
    expect(dialog.textContent).toContain(
      "the app’s name and version, your operating system and its architecture, and no ID"
    )
    expect(dialog.textContent).toContain(
      "asks github.com instead, sending only your IP address and the app’s name"
    )
    // Every host the answer reaches, the download's included.
    expect(dialog.textContent).toContain(
      "githubusercontent.com, also sees your IP address"
    )
    expect(dialog.textContent).toContain("the next time you quit")
  })

  it("describes GitHub's releases for an app whose updater reads them directly", async () => {
    render(<EgressPrompt />)

    void askEgress({
      destination: "app_updates",
      host: "github.com",
      purpose: "github_releases",
      allow: async () => undefined,
    })

    const dialog = await screen.findByRole("alertdialog", {
      name: "Allow SurfSense to check for updates?",
    })
    expect(dialog.textContent).toContain(
      "reads the list of releases on github.com"
    )
    expect(dialog.textContent).toContain("githubusercontent.com")
    expect(dialog.textContent).not.toContain("updates.surfsense.com")
  })

  it("names a policy's mirror as the only update host", async () => {
    render(<EgressPrompt />)

    void askEgress({
      destination: "app_updates",
      host: "updates.example.org",
      purpose: "update_mirror",
      allow: async () => undefined,
    })

    const dialog = await screen.findByRole("alertdialog", {
      name: "Allow SurfSense to check for updates?",
    })
    expect(dialog.textContent).toContain(
      "the update server your organization set"
    )
    expect(dialog.textContent).not.toContain("github.com")
  })

  it.each(["plugin_registry", "plugin"])(
    "says SurfSense's plugin host gets the license key for paid plugins (%s)",
    async (purpose) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () =>
          Response.json(
            {
              detail: {
                code: "egress_disabled",
                message: "off",
                destination: "host:plugins.surfsense.com",
                host: "plugins.surfsense.com",
                purpose,
              },
            },
            { status: 403 }
          )
        )
      )
      render(<EgressPrompt />)

      void requestVoid("/plugins/registry/1", { method: "POST" }).catch(
        () => {}
      )

      const dialog = await screen.findByRole("alertdialog")
      expect(dialog.textContent).toContain("your license key")
    }
  )

  it("asks about downloading the license’s jobs, names both of the license server’s errands, and downloads on Allow", async () => {
    const calls: string[] = []
    let allowed = false
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        calls.push(`${init?.method ?? "GET"} ${path}`)
        if (path === "/egress" && init?.method === "PUT") {
          calls[calls.length - 1] +=
            ` ${JSON.parse(String(init.body)).destinations.join(",")}`
          allowed = true
          return Response.json([])
        }
        return allowed
          ? Response.json({ outcomes: [], packs: [] })
          : Response.json(
              {
                detail: {
                  code: "egress_disabled",
                  message: "off",
                  destination: "host:api.surfsense.com",
                  host: "api.surfsense.com",
                  hosts: ["api.surfsense.com"],
                  purpose: "job_packs",
                },
              },
              { status: 403 }
            )
      })
    )
    const user = userEvent.setup()
    render(<EgressPrompt />)

    const pending = requestVoid("/job-packs/download", { method: "POST" })
    const prompt = await screen.findByRole("alertdialog", {
      name: "Allow downloading your jobs?",
    })
    // One server, two errands: the license's file and its jobs, and what each sends.
    expect(prompt.textContent).toContain(
      "api.surfsense.com, its license server, for your license’s latest file and for the jobs your license includes, sending your license key and your IP address"
    )
    expect(prompt.textContent).toContain(
      "A job download also sends the job’s code, the version you already have and the kinds of job this version of SurfSense can run."
    )
    expect(prompt.textContent).toContain(
      "for newer versions of your jobs, while a license with jobs is active"
    )
    // A job's check that a run held back is made again once the run ends.
    expect(prompt.textContent).toContain(
      "A check for a job that comes during a run of it is made again once the run ends."
    )
    await user.click(screen.getByRole("button", { name: "Allow" }))

    await expect(pending).resolves.toBeUndefined()
    expect(calls).toEqual([
      "POST /job-packs/download",
      "PUT /egress host:api.surfsense.com",
      "POST /job-packs/download",
    ])
  })

  it("asks about reaching the license server when a refusal names no errand", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              code: "egress_disabled",
              message: "off",
              destination: "host:api.surfsense.com",
              host: "api.surfsense.com",
            },
          },
          { status: 403 }
        )
      )
    )
    render(<EgressPrompt />)

    // Its purpose left out, the question cannot say which errand it is for.
    void requestVoid("/job-packs/download", { method: "POST" }).catch(() => {})

    const dialog = await screen.findByRole("alertdialog", {
      name: "Allow reaching SurfSense’s license server?",
    })
    expect(dialog.textContent).toContain(
      "api.surfsense.com, its license server"
    )
  })

  it("never mentions a license key to a third-party plugin's host", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              code: "egress_disabled",
              message: "off",
              destination: "host:mcp.notes.example",
              host: "mcp.notes.example",
              purpose: "plugin",
            },
          },
          { status: 403 }
        )
      )
    )
    render(<EgressPrompt />)

    void requestVoid("/plugins/custom", { method: "POST" }).catch(() => {})

    const dialog = await screen.findByRole("alertdialog")
    expect(dialog.textContent).not.toContain("license key")
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
