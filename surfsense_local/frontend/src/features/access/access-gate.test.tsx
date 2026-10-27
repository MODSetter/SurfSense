import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"
import { request } from "@/lib/api"

import { AccessGate } from "./access-gate"

type State = { password: boolean; signedIn: boolean; host: boolean }

/** The access service as Caddy serves it: /access/* on the page's own origin. */
function serve(state: State, signIn: (password: string) => Response) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/access/state") return Response.json(state)
      if (path === "/access/sign-in") {
        const { password } = JSON.parse(String(init?.body)) as {
          password: string
        }
        const answer = signIn(password)
        if (answer.status === 204) state.signedIn = true
        return answer
      }
      if (path === "/api/documents") {
        return new Response(null, { status: state.signedIn ? 200 : 401 })
      }
      return new Response(null, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

const right = (password: string) =>
  new Response(null, {
    status: password === "correct horse battery" ? 204 : 401, // pragma: allowlist secret
  })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the access gate in the Docker image", { tags: ["docker"] }, () => {
  it("opens the app without a sign-in while no password exists", async () => {
    serve({ password: false, signedIn: false, host: true }, right)
    render(<AccessGate>the app</AccessGate>)

    expect(await screen.findByText("the app")).toBeTruthy()
  })

  it("asks for the password, and opens the app once it is right", async () => {
    serve({ password: true, signedIn: false, host: false }, right)
    const user = userEvent.setup()
    render(<AccessGate>the app</AccessGate>)

    await user.type(await screen.findByLabelText("Password"), "nope")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("That password isn’t right.")).toBeTruthy()
    expect(screen.queryByText("the app")).toBeNull()

    await user.clear(screen.getByLabelText("Password"))
    await user.type(screen.getByLabelText("Password"), "correct horse battery")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("the app")).toBeTruthy()
  })

  it("says how long to wait after too many wrong passwords", async () => {
    serve(
      { password: true, signedIn: false, host: false },
      () =>
        new Response(null, { status: 429, headers: { "Retry-After": "42" } })
    )
    const user = userEvent.setup()
    render(<AccessGate>the app</AccessGate>)

    await user.type(await screen.findByLabelText("Password"), "anything")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(
      await screen.findByText("Too many tries. Try again in 42 seconds.")
    ).toBeTruthy()
  })

  it("returns to the sign-in when the API says the session ended", async () => {
    const state = { password: true, signedIn: true, host: false }
    serve(state, right)
    render(<AccessGate>the app</AccessGate>)
    expect(await screen.findByText("the app")).toBeTruthy()

    // Signed out elsewhere, or the password changed: the next request is refused.
    state.signedIn = false
    await act(() => request("/documents").catch(() => undefined))

    expect(await screen.findByLabelText("Password")).toBeTruthy()
    expect(screen.queryByText("the app")).toBeNull()
  })
})
