import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { AccessState } from "./api"
import { AccessSettings } from "./access-settings"

const PASSWORD = "correct horse battery" // pragma: allowlist secret

function state(overrides: Partial<AccessState> = {}): AccessState {
  return {
    password: true,
    signedIn: true,
    host: false,
    source: "app",
    signInOff: false,
    ...overrides,
  }
}

function serve(current: AccessState) {
  const sent: { path: string; body: unknown }[] = []
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/access/state") return Response.json(current)
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      sent.push({ path, body })
      if (path === "/access/password") {
        const { current: given } = body as { current?: string }
        if (given !== PASSWORD) return new Response(null, { status: 403 })
        return new Response(null, { status: 204 })
      }
      if (path === "/access/sign-out")
        return new Response(null, { status: 204 })
      return new Response(null, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  // Signing out reloads the page into the sign-in.
  const reload = vi.fn()
  vi.stubGlobal("location", { ...window.location, reload })
  return { sent, reload }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Settings › Access in the Docker image", { tags: ["docker"] }, () => {
  it("changes the password with the current one and one new one", async () => {
    const { sent } = serve(state())
    const user = userEvent.setup()
    render(<AccessSettings />)

    expect(screen.queryByLabelText("Confirm password")).toBeNull()
    await user.type(
      await screen.findByLabelText("Current password"),
      "wrong one!"
    )
    await user.type(
      screen.getByLabelText("New password"),
      "a new long passphrase"
    )
    await user.click(screen.getByRole("button", { name: "Change password" }))
    expect(
      await screen.findByText("The current password isn’t right.")
    ).toBeTruthy()

    await user.clear(screen.getByLabelText("Current password"))
    await user.type(screen.getByLabelText("Current password"), PASSWORD)
    await user.click(screen.getByRole("button", { name: "Change password" }))
    expect(
      await screen.findByText(
        "Password changed. Other devices must sign in again."
      )
    ).toBeTruthy()
    expect(sent.at(-1)).toEqual({
      path: "/access/password",
      body: { current: PASSWORD, password: "a new long passphrase" }, // pragma: allowlist secret
    })
  })

  it("refuses a new password shorter than eight characters before sending it", async () => {
    const { sent } = serve(state())
    const user = userEvent.setup()
    render(<AccessSettings />)

    await user.type(await screen.findByLabelText("Current password"), PASSWORD)
    await user.type(screen.getByLabelText("New password"), "short")
    await user.click(screen.getByRole("button", { name: "Change password" }))
    expect(await screen.findByText("Use at least 8 characters.")).toBeTruthy()
    expect(sent).toEqual([])
  })

  it("shows a password from the server's setup as locked, with nothing to change", async () => {
    serve(state({ source: "setup" }))
    render(<AccessSettings />)

    expect(
      await screen.findByText(
        "This password is set where SurfSense is installed. To change it, update SurfSense’s setup on that computer, then restart it."
      )
    ).toBeTruthy()
    expect(screen.queryByLabelText("New password")).toBeNull()
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy()
  })

  it("says when the server turned sign-in off, with no password to manage", async () => {
    serve(
      state({ password: false, source: null, signedIn: false, signInOff: true })
    )
    render(<AccessSettings />)

    expect(
      await screen.findByText(
        "Sign-in is turned off where SurfSense is installed. Anyone who can reach it can use it."
      )
    ).toBeTruthy()
    expect(screen.queryByLabelText("New password")).toBeNull()
    expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull()
  })

  it("signs this browser out", async () => {
    const { sent, reload } = serve(state())
    const user = userEvent.setup()
    render(<AccessSettings />)

    await user.click(await screen.findByRole("button", { name: "Sign out" }))
    expect(sent.map((call) => call.path)).toEqual(["/access/sign-out"])
    expect(reload).toHaveBeenCalled()
  })
})
