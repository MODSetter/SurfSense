import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { AccessSettings } from "./access-settings"

type State = { password: boolean; signedIn: boolean; host: boolean }

function serve(state: State) {
  const sent: { path: string; body: unknown }[] = []
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/access/state") return Response.json(state)
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      sent.push({ path, body })
      if (path === "/access/password") {
        const { current } = body as { current?: string }
        if (state.password && current !== "correct horse battery") {
          return new Response(null, { status: 403 })
        }
        state.password = true
        state.signedIn = true
        return new Response(null, { status: 204 })
      }
      if (path === "/access/sign-out") {
        state.signedIn = false
        return new Response(null, { status: 204 })
      }
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
  it("creates the first password, matching its confirmation", async () => {
    const { sent } = serve({ password: false, signedIn: false, host: true })
    const user = userEvent.setup()
    render(<AccessSettings />)

    await user.type(
      await screen.findByLabelText("New password"),
      "correct horse battery"
    )
    await user.type(
      screen.getByLabelText("Confirm password"),
      "correct horse batterz"
    )
    await user.click(screen.getByRole("button", { name: "Create password" }))
    expect(await screen.findByText("The passwords don’t match.")).toBeTruthy()
    expect(sent).toEqual([])

    await user.clear(screen.getByLabelText("Confirm password"))
    await user.type(
      screen.getByLabelText("Confirm password"),
      "correct horse battery"
    )
    await user.click(screen.getByRole("button", { name: "Create password" }))
    expect(
      await screen.findByRole("button", { name: "Change password" })
    ).toBeTruthy()
    expect(sent).toEqual([
      { path: "/access/password", body: { password: "correct horse battery" } }, // pragma: allowlist secret
    ])
  })

  it("refuses a password shorter than eight characters before sending it", async () => {
    const { sent } = serve({ password: false, signedIn: false, host: true })
    const user = userEvent.setup()
    render(<AccessSettings />)

    await user.type(await screen.findByLabelText("New password"), "short")
    await user.type(screen.getByLabelText("Confirm password"), "short")
    await user.click(screen.getByRole("button", { name: "Create password" }))
    expect(await screen.findByText("Use at least 8 characters.")).toBeTruthy()
    expect(sent).toEqual([])
  })

  it("changes the password only with the current one", async () => {
    serve({ password: true, signedIn: true, host: false })
    const user = userEvent.setup()
    render(<AccessSettings />)

    await user.type(
      await screen.findByLabelText("Current password"),
      "wrong one!"
    )
    await user.type(
      screen.getByLabelText("New password"),
      "a new long passphrase"
    )
    await user.type(
      screen.getByLabelText("Confirm password"),
      "a new long passphrase"
    )
    await user.click(screen.getByRole("button", { name: "Change password" }))
    expect(
      await screen.findByText("The current password isn’t right.")
    ).toBeTruthy()

    await user.clear(screen.getByLabelText("Current password"))
    await user.type(
      screen.getByLabelText("Current password"),
      "correct horse battery"
    )
    await user.click(screen.getByRole("button", { name: "Change password" }))
    expect(
      await screen.findByText(
        "Password changed. Other devices must sign in again."
      )
    ).toBeTruthy()
  })

  it("signs this browser out", async () => {
    const { sent, reload } = serve({
      password: true,
      signedIn: true,
      host: false,
    })
    const user = userEvent.setup()
    render(<AccessSettings />)

    await user.click(await screen.findByRole("button", { name: "Sign out" }))
    expect(sent.map((call) => call.path)).toEqual(["/access/sign-out"])
    expect(reload).toHaveBeenCalled()
  })
})
