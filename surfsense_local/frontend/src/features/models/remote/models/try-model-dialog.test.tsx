import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { ConnectionModel } from "./api"
import { TryModelDialog } from "./try-model-dialog"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const FABLE: ConnectionModel = {
  connection_id: 3,
  connection_label: "Claude plan",
  name: "claude-fable-5-1",
  types: ["text_gen"],
  capability_source: "catalog",
  selectable_for: ["text_gen"],
  reads_images: true,
}

function open(plan: boolean) {
  render(
    <TryModelDialog
      open
      modelType="text_gen"
      model={FABLE}
      unlisted={false}
      plan={plan}
      onOpenChange={vi.fn()}
      onOpenChangeComplete={vi.fn()}
    />
  )
}

describe("what testing a chat model costs", () => {
  it("counts toward a plan's limits, and costs no money, on a plan", async () => {
    open(true)

    const dialog = await screen.findByRole("dialog")
    expect(dialog.textContent).toContain("counts toward your plan’s limits")
    expect(dialog.textContent).not.toContain("may cost money")
  })

  it("may cost money on a server that bills per request", async () => {
    open(false)

    expect((await screen.findByRole("dialog")).textContent).toContain(
      "may cost money"
    )
  })
})

const ELEVEN: ConnectionModel = {
  connection_id: 2,
  connection_label: "OpenRouter",
  name: "elevenlabs/eleven-v4",
  types: ["audio_gen"],
  capability_source: "declared",
  selectable_for: ["audio_gen"],
  reads_images: false,
  voices: [
    { id: "george", label: "george" },
    { id: "sarah", label: "sarah" },
  ],
}

function openVoiceTrial(model: ConnectionModel) {
  const sent: { voice?: string }[] = []
  vi.stubGlobal(
    "URL",
    Object.assign(URL, { createObjectURL: () => "blob:clip" })
  )
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      sent.push(JSON.parse(String(init?.body)))
      return new Response(new Blob(["clip"], { type: "audio/wav" }))
    })
  )
  render(
    <TryModelDialog
      open
      modelType="audio_gen"
      model={model}
      unlisted={false}
      onOpenChange={vi.fn()}
      onOpenChangeComplete={vi.fn()}
    />
  )
  return sent
}

describe("trying a voice on a model that publishes them", () => {
  it("starts on its first voice, so the first test can succeed", async () => {
    const user = userEvent.setup()
    const sent = openVoiceTrial(ELEVEN)

    await user.click(await screen.findByRole("button", { name: "Test voice" }))

    await waitFor(() => expect(sent[0]?.voice).toBe("george"))
  })

  it("lists the model's voices, and every one stays on offer once chosen", async () => {
    const user = userEvent.setup()
    const sent = openVoiceTrial(ELEVEN)
    const field = await screen.findByRole("combobox", { name: "Voice" })

    await user.click(field)
    await user.click(await screen.findByRole("option", { name: "sarah" }))
    await user.click(field)

    expect(await screen.findByRole("option", { name: "george" })).toBeTruthy()
    await user.keyboard("{Escape}")
    await user.click(screen.getByRole("button", { name: "Test voice" }))
    await waitFor(() => expect(sent[0]?.voice).toBe("sarah"))
  })

  it("still voices an id it does not list", async () => {
    const user = userEvent.setup()
    const sent = openVoiceTrial(ELEVEN)
    const field = await screen.findByRole("combobox", { name: "Voice" })

    await user.clear(field)
    await user.type(field, "OZ0L6")
    await user.keyboard("{Escape}")
    await user.click(screen.getByRole("button", { name: "Test voice" }))

    await waitFor(() => expect(sent[0]?.voice).toBe("OZ0L6"))
  })

  it("holds the test while no voice is named, since the server needs one", async () => {
    const user = userEvent.setup()
    openVoiceTrial(ELEVEN)

    await user.clear(await screen.findByRole("combobox", { name: "Voice" }))
    await user.keyboard("{Escape}")

    expect(
      screen
        .getByRole("button", { name: "Test voice" })
        .hasAttribute("disabled")
    ).toBe(true)
  })
})

describe("trying a voice the server names", () => {
  const NAMED = {
    ...ELEVEN,
    voices: [
      { id: "JBFqnCBsd6", label: "George" },
      { id: "EXAVITQu4v", label: "Sarah" },
    ],
  }

  it("shows the name and sends the id", async () => {
    const user = userEvent.setup()
    const sent = openVoiceTrial(NAMED)
    const field = await screen.findByRole("combobox", { name: "Voice" })
    expect((field as HTMLInputElement).value).toBe("George")

    await user.click(field)
    await user.click(await screen.findByRole("option", { name: "Sarah" }))
    expect((field as HTMLInputElement).value).toBe("Sarah")
    await user.click(screen.getByRole("button", { name: "Test voice" }))

    await waitFor(() => expect(sent[0]?.voice).toBe("EXAVITQu4v"))
  })

  it("still takes a typed id", async () => {
    const user = userEvent.setup()
    const sent = openVoiceTrial(NAMED)
    const field = await screen.findByRole("combobox", { name: "Voice" })

    await user.clear(field)
    await user.type(field, "OZ0L6")
    await user.keyboard("{Escape}")
    await user.click(screen.getByRole("button", { name: "Test voice" }))

    await waitFor(() => expect(sent[0]?.voice).toBe("OZ0L6"))
  })
})

describe("trying a voice on a model that publishes none", () => {
  it("keeps the plain box, where empty leaves it to the server's default", async () => {
    const user = userEvent.setup()
    const sent = openVoiceTrial({ ...ELEVEN, voices: [] })

    expect(await screen.findByRole("textbox", { name: "Voice" })).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Test voice" }))

    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0]?.voice ?? "").toBe("")
  })
})
