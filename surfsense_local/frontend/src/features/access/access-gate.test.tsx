import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"
import { request } from "@/lib/api"

import type { AccessState } from "./api"
import { AccessGate } from "./access-gate"

const PASSWORD = "correct horse battery" // pragma: allowlist secret

function state(overrides: Partial<AccessState> = {}): AccessState {
  return {
    password: true,
    signedIn: false,
    host: false,
    source: "app",
    signInOff: false,
    ...overrides,
  }
}

/** The access service as Caddy serves it: /access/* on the page's own origin. */
function serve(current: AccessState, signIn: (password: string) => Response) {
  const created: unknown[] = []
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/access/state") return Response.json(current)
      if (path === "/access/sign-in") {
        const { password } = JSON.parse(String(init?.body)) as {
          password: string
        }
        const answer = signIn(password)
        if (answer.status === 204) current.signedIn = true
        return answer
      }
      if (path === "/access/password") {
        created.push(JSON.parse(String(init?.body)))
        Object.assign(current, { password: true, signedIn: true })
        return new Response(null, { status: 204 })
      }
      if (path === "/api/documents") {
        return new Response(null, { status: current.signedIn ? 200 : 401 })
      }
      return new Response(null, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return { created }
}

const right = (password: string) =>
  new Response(null, { status: password === PASSWORD ? 204 : 401 })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the access gate in the Docker image", { tags: ["docker"] }, () => {
  it("sets SurfSense up with one password, then opens the app", async () => {
    const { created } = serve(state({ password: false, source: null }), right)
    const user = userEvent.setup()
    render(<AccessGate>the app</AccessGate>)

    expect(
      await screen.findByRole("heading", { name: "Set up SurfSense" })
    ).toBeTruthy()
    // One field: the eye shows what was typed, in place of typing it twice.
    expect(screen.queryByLabelText("Confirm password")).toBeNull()
    await user.type(screen.getByLabelText("Password"), PASSWORD)
    await user.click(screen.getByRole("button", { name: "Create password" }))

    expect(await screen.findByText("the app")).toBeTruthy()
    expect(created).toEqual([{ password: PASSWORD }])
  })

  it("shows the password while asked to, so a typo is caught", async () => {
    serve(state({ password: false, source: null }), right)
    const user = userEvent.setup()
    render(<AccessGate>the app</AccessGate>)
    const field = await screen.findByLabelText("Password")

    expect(field.getAttribute("type")).toBe("password")
    expect(field.getAttribute("autocomplete")).toBe("new-password")
    await user.click(screen.getByRole("button", { name: "Show password" }))
    expect(field.getAttribute("type")).toBe("text")
  })

  it("opens the app at once when the server turned sign-in off", async () => {
    serve(state({ password: false, source: null, signInOff: true }), right)
    render(<AccessGate>the app</AccessGate>)

    expect(await screen.findByText("the app")).toBeTruthy()
  })

  it("asks for the password, and opens the app once it is right", async () => {
    serve(state(), right)
    const user = userEvent.setup()
    render(<AccessGate>the app</AccessGate>)

    await user.type(await screen.findByLabelText("Password"), "nope")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("That password isn’t right.")).toBeTruthy()
    expect(screen.queryByText("the app")).toBeNull()

    await user.clear(screen.getByLabelText("Password"))
    await user.type(screen.getByLabelText("Password"), PASSWORD)
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("the app")).toBeTruthy()
  })

  it("says how long to wait after too many wrong passwords", async () => {
    serve(
      state(),
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
    const current = state({ signedIn: true })
    serve(current, right)
    render(<AccessGate>the app</AccessGate>)
    expect(await screen.findByText("the app")).toBeTruthy()

    // Signed out elsewhere, or the password changed: the next request is refused.
    current.signedIn = false
    await act(() => request("/documents").catch(() => undefined))

    expect(await screen.findByLabelText("Password")).toBeTruthy()
    expect(screen.queryByText("the app")).toBeNull()
  })
})
