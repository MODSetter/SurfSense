import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ConnectionForm } from "../connection-form"

const AUTHORIZE = "https://auth.openai.com/api/accounts/authorize?state=s"

const SIGNED_IN = {
  id: 4,
  label: "ChatGPT",
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
}

const SIGNED_OUT = { ...SIGNED_IN, signed_in: false, account_email: null }

function serve(outcome: "signed_in" | "failed") {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/catalog/remote") return Response.json([])
      if (path === "/llm/connections/chatgpt")
        return Response.json({ serves: ["text_gen"], hosts: [] })
      if (
        path === "/llm/connections/chatgpt/sign-in" &&
        init?.method === "POST"
      )
        return Response.json(
          { flow_id: "f1", authorize_url: AUTHORIZE },
          { status: 201 }
        )
      if (path === "/llm/connections/chatgpt/sign-in/f1")
        return Response.json(
          outcome === "signed_in"
            ? { status: "signed_in", connection_id: 4, message: null }
            : {
                status: "failed",
                connection_id: null,
                message: "The sign-in was declined.",
              }
        )
      if (path === "/llm/connections") return Response.json([SIGNED_IN])
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("signing a ChatGPT connection in again", () => {
  it("asks for no URL or key, signs in in the browser, and saves the connection", async () => {
    const fetchMock = serve("signed_in")
    const openExternal = vi.fn(async () => {})
    window.surfsense = { openExternal } as unknown as typeof window.surfsense
    const onSaved = vi.fn()
    const user = userEvent.setup()
    render(
      <ConnectionForm
        connection={SIGNED_OUT as never}
        onCancel={vi.fn()}
        onSaved={onSaved}
      />
    )

    expect(screen.queryByLabelText("Base URL")).toBeNull()
    expect(screen.queryByLabelText("API key")).toBeNull()
    await user.click(screen.getByRole("button", { name: "Sign in again" }))

    await waitFor(() => expect(openExternal).toHaveBeenCalledWith(AUTHORIZE))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(SIGNED_IN), {
      timeout: 8000,
    })
    const started = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/connections/chatgpt/sign-in" && init?.method === "POST"
    )
    expect(JSON.parse(String(started?.[1]?.body))).toEqual({
      connection_id: 4,
    })
  })

  it("says a sign-in failed and lets it be tried again", async () => {
    serve("failed")
    window.surfsense = {
      openExternal: vi.fn(async () => {}),
    } as unknown as typeof window.surfsense
    const user = userEvent.setup()
    render(
      <ConnectionForm
        connection={SIGNED_OUT as never}
        onCancel={vi.fn()}
        onSaved={vi.fn()}
      />
    )

    await user.click(screen.getByRole("button", { name: "Sign in again" }))

    expect(
      await screen.findByText("The sign-in was declined.", undefined, {
        timeout: 8000,
      })
    ).toBeTruthy()
    expect(
      screen
        .getByRole("button", { name: "Sign in again" })
        .hasAttribute("disabled")
    ).toBe(false)
  })
})

const RETURNED = "http://127.0.0.1:4929/callback?code=c&state=s"

/** The same API under the image's /api base; the flow waits until the address is pasted. */
function serveRemote() {
  let pasted = false
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace(/^\/api/, "")
      if (path === "/llm/catalog/remote") return Response.json([])
      if (path === "/llm/connections/chatgpt")
        return Response.json({ serves: ["text_gen"], hosts: [] })
      if (
        path === "/llm/connections/chatgpt/sign-in" &&
        init?.method === "POST"
      )
        return Response.json(
          { flow_id: "f1", authorize_url: AUTHORIZE },
          { status: 201 }
        )
      if (path === "/llm/connections/chatgpt/sign-in/f1/callback") {
        pasted = true
        return new Response(null, { status: 204 })
      }
      if (path === "/llm/connections/chatgpt/sign-in/f1")
        return Response.json(
          pasted
            ? { status: "signed_in", connection_id: 4, message: null }
            : { status: "waiting", connection_id: null, message: null }
        )
      if (path === "/llm/connections") return Response.json([SIGNED_IN])
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  vi.stubGlobal("open", vi.fn())
  return fetchMock
}

describe(
  "signing in to ChatGPT from another device than the Docker host",
  { tags: ["docker"] },
  () => {
    it("takes the address the browser was sent to, and saves the connection", async () => {
      const fetchMock = serveRemote()
      vi.stubGlobal("location", {
        ...window.location,
        hostname: "surfsense.lan",
      })
      const onSaved = vi.fn()
      const user = userEvent.setup()
      render(
        <ConnectionForm
          connection={SIGNED_OUT as never}
          onCancel={vi.fn()}
          onSaved={onSaved}
        />
      )

      await user.click(screen.getByRole("button", { name: "Sign in again" }))
      await user.type(
        await screen.findByLabelText("Address your browser ended on"),
        RETURNED
      )
      await user.click(
        screen.getByRole("button", { name: "Finish signing in" })
      )

      await waitFor(() => expect(onSaved).toHaveBeenCalledWith(SIGNED_IN), {
        timeout: 8000,
      })
      const pasted = fetchMock.mock.calls.find(([path]) =>
        String(path).endsWith("/sign-in/f1/callback")
      )
      expect(JSON.parse(String(pasted?.[1]?.body))).toEqual({
        address: RETURNED,
      })
    })

    it("asks for nothing on the Docker host itself, where the redirect lands", async () => {
      serveRemote()
      const user = userEvent.setup()
      render(
        <ConnectionForm
          connection={SIGNED_OUT as never}
          onCancel={vi.fn()}
          onSaved={vi.fn()}
        />
      )

      await user.click(screen.getByRole("button", { name: "Sign in again" }))
      expect(
        await screen.findByText("Finish signing in in your browser.")
      ).toBeTruthy()
      expect(
        screen.queryByLabelText("Address your browser ended on")
      ).toBeNull()
    })
  }
)
