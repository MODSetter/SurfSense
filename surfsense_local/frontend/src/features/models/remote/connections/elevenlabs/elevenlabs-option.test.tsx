import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ConnectionDialog } from "../connection-dialog"
import type { Connection } from "../api"
import { ElevenLabsOption } from "./elevenlabs-option"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const CONNECTED: Connection = {
  id: 7,
  label: "ElevenLabs",
  provider: "openai_compatible",
  base_url: "https://api.elevenlabs.io",
  catalog_provider: "custom",
  has_api_key: true,
  auth_kind: "elevenlabs",
  signed_in: false,
  account_email: null,
  serves: ["audio_gen"],
  created_at: "2026-11-05T00:00:00Z",
  updated_at: "2026-11-05T00:00:00Z",
}

/** The backend's routes; `refusal` is the sentence a key is refused with. */
function serve({
  connections = [],
  refusal,
}: { connections?: Connection[]; refusal?: string } = {}) {
  const sent: { path: string; method: string; body: unknown }[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (path === "/llm/connections/elevenlabs" && method === "GET") {
        return Response.json({ serves: ["audio_gen"] })
      }
      if (path === "/llm/connections" && method === "GET") {
        return Response.json(connections)
      }
      const body = init?.body ? JSON.parse(String(init.body)) : null
      sent.push({ path, method, body })
      if (refusal) {
        return Response.json(
          { detail: { code: "elevenlabs_refused", message: refusal } },
          { status: 422 }
        )
      }
      return Response.json(CONNECTED, { status: method === "POST" ? 201 : 200 })
    })
  )
  return sent
}

describe("connecting ElevenLabs", () => {
  it("is offered only where the backend says it fills the slot", async () => {
    serve()
    const { rerender } = render(
      <ElevenLabsOption modelType="audio_gen" onConnected={vi.fn()} />
    )
    expect(
      await screen.findByRole("region", { name: "Use ElevenLabs" })
    ).toBeTruthy()

    rerender(<ElevenLabsOption modelType="text_gen" onConnected={vi.fn()} />)
    expect(screen.queryByRole("region", { name: "Use ElevenLabs" })).toBeNull()
  })

  it("takes a name and a key, and hands over what it saved", async () => {
    const sent = serve()
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ElevenLabsOption modelType="audio_gen" onConnected={onConnected} />)

    await user.click(await screen.findByRole("button", { name: "Connect" }))
    const dialog = await screen.findByRole("dialog")
    expect(dialog.textContent).toContain("Text to Speech, Models and Voices")
    const save = screen.getByRole("button", { name: "Connect ElevenLabs" })
    expect(save.hasAttribute("disabled")).toBe(true)
    await user.type(screen.getByLabelText("API key"), "sk_abc")
    await user.click(save)

    await waitFor(() =>
      expect(onConnected).toHaveBeenCalledWith(
        expect.objectContaining({ id: 7 })
      )
    )
    expect(sent).toEqual([
      {
        path: "/llm/connections/elevenlabs",
        method: "POST",
        body: { label: "ElevenLabs", api_key: "sk_abc" }, // pragma: allowlist secret
      },
    ])
  })

  it("shows why a key was refused, and keeps the dialog open to fix it", async () => {
    const refusal = "The API key is missing the permission voices_read."
    serve({ refusal })
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ElevenLabsOption modelType="audio_gen" onConnected={onConnected} />)

    await user.click(await screen.findByRole("button", { name: "Connect" }))
    await user.type(await screen.findByLabelText("API key"), "sk_abc")
    await user.click(screen.getByRole("button", { name: "Connect ElevenLabs" }))

    expect(await screen.findByText(refusal)).toBeTruthy()
    expect(onConnected).not.toHaveBeenCalled()
    expect(screen.getByRole("dialog")).toBeTruthy()
  })

  it("opens the models of a connection it already has", async () => {
    serve({ connections: [CONNECTED] })
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ElevenLabsOption modelType="audio_gen" onConnected={onConnected} />)

    await user.click(await screen.findByRole("button", { name: "Show models" }))

    expect(onConnected).toHaveBeenCalledWith(CONNECTED)
  })
})

describe("editing an ElevenLabs connection", () => {
  it("offers its name and key, never a provider or an address", async () => {
    const sent = serve()
    const user = userEvent.setup()
    render(
      <ConnectionDialog open connection={CONNECTED} onOpenChange={vi.fn()} />
    )

    const name = await screen.findByLabelText("Name")
    expect(screen.queryByLabelText("Base URL")).toBeNull()
    expect(screen.queryByLabelText("Provider")).toBeNull()
    await user.clear(name)
    await user.type(name, "Studio voices")
    await user.click(screen.getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0].path).toBe("/llm/connections/7")
    expect(sent[0].method).toBe("PUT")
    // No key typed, so the saved one stays.
    expect(sent[0].body).not.toHaveProperty("api_key")
    expect(sent[0].body).toMatchObject({ label: "Studio voices" })
  })

  it("sends a key only when one was typed", async () => {
    const sent = serve()
    const user = userEvent.setup()
    render(
      <ConnectionDialog open connection={CONNECTED} onOpenChange={vi.fn()} />
    )

    await user.type(await screen.findByLabelText("API key"), "sk_new")
    await user.click(screen.getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0].body).toMatchObject({ api_key: "sk_new" }) // pragma: allowlist secret
  })
})
