import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { Connection } from "../api"
import { ChatGPTOption } from "./chatgpt-option"

const AUTHORIZE = "https://auth.openai.com/api/accounts/authorize?state=s"

const SIGNED_IN: Connection = {
  id: 4,
  label: "ChatGPT subscription",
  provider: "openai_compatible",
  base_url: "https://api.openai.com/v1",
  catalog_provider: "openai",
  has_api_key: false,
  serves: ["text_gen"],
  auth_kind: "chatgpt",
  signed_in: true,
  account_email: "reader@example.com",
  created_at: "2026-10-02T00:00:00",
  updated_at: "2026-10-02T00:00:00",
} as Connection

function serve({
  outcome = "signed_in",
  serves = ["text_gen"],
  connected = false,
}: {
  outcome?: "signed_in" | "failed" | "waiting"
  serves?: string[]
  /** A plan connected before the test, rather than by its sign-in. */
  connected?: boolean
} = {}) {
  let signedIn = connected
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/connections/chatgpt")
        return Response.json({ serves, hosts: [] })
      if (
        path === "/llm/connections/chatgpt/sign-in" &&
        init?.method === "POST"
      )
        return Response.json(
          { flow_id: "f1", authorize_url: AUTHORIZE },
          { status: 201 }
        )
      if (path === "/llm/connections/chatgpt/sign-in/f1") {
        if (init?.method === "DELETE")
          return new Response(null, { status: 204 })
        if (outcome === "waiting")
          return Response.json({
            status: "waiting",
            connection_id: null,
            message: null,
          })
        if (outcome === "signed_in") signedIn = true
        return Response.json(
          outcome === "signed_in"
            ? { status: "signed_in", connection_id: 4, message: null }
            : {
                status: "failed",
                connection_id: null,
                message: "The sign-in was declined.",
              }
        )
      }
      if (path === "/llm/connections")
        return Response.json(signedIn ? [SIGNED_IN] : [])
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  window.surfsense = {
    openExternal: vi.fn(async () => {}),
  } as unknown as typeof window.surfsense
  return fetchMock
}

const signInButton = () =>
  screen.findByRole("button", { name: "Sign in with ChatGPT" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("the ChatGPT option beside Use a server", () => {
  it("is offered only where a ChatGPT plan can fill the slot", async () => {
    serve({ serves: ["text_gen"] })
    render(<ChatGPTOption modelType="video_gen" onConnected={vi.fn()} />)
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Use your ChatGPT plan" })
      ).toBeNull()
    )
  })

  it("signs in with one click and hands over the new connection", async () => {
    const fetchMock = serve()
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ChatGPTOption modelType="text_gen" onConnected={onConnected} />)

    await user.click(await signInButton())

    await waitFor(() =>
      expect(window.surfsense?.openExternal).toHaveBeenCalledWith(AUTHORIZE)
    )
    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(SIGNED_IN), {
      timeout: 8000,
    })
    const started = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/connections/chatgpt/sign-in" && init?.method === "POST"
    )
    expect(JSON.parse(String(started?.[1]?.body))).toEqual({
      label: "ChatGPT subscription",
    })
  })

  it("says to finish in the browser, and Cancel gives the button back", async () => {
    const fetchMock = serve({ outcome: "waiting" })
    const user = userEvent.setup()
    render(<ChatGPTOption modelType="text_gen" onConnected={vi.fn()} />)

    await user.click(await signInButton())
    expect(
      await screen.findByText("Finish signing in in your browser.")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    expect(await signInButton()).toBeTruthy()
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) =>
          path === "/llm/connections/chatgpt/sign-in/f1" &&
          init?.method === "DELETE"
      )
    ).toBe(true)
  })

  it("says a sign-in failed and lets it be tried again", async () => {
    serve({ outcome: "failed" })
    const user = userEvent.setup()
    render(<ChatGPTOption modelType="text_gen" onConnected={vi.fn()} />)

    await user.click(await signInButton())

    expect(
      await screen.findByText("The sign-in was declined.", undefined, {
        timeout: 8000,
      })
    ).toBeTruthy()
    expect((await signInButton()).hasAttribute("disabled")).toBe(false)
  })

  it("shows the plan's models when an account is already connected", async () => {
    const fetchMock = serve({ connected: true })
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ChatGPTOption modelType="text_gen" onConnected={onConnected} />)

    expect(
      await screen.findByText("Connected as reader@example.com")
    ).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Sign in with ChatGPT" })
    ).toBeNull()
    await user.click(screen.getByRole("button", { name: "Show models" }))

    expect(onConnected).toHaveBeenCalledWith(SIGNED_IN)
    expect(
      fetchMock.mock.calls.some(
        ([path]) => path === "/llm/connections/chatgpt/sign-in"
      )
    ).toBe(false)
  })
})
