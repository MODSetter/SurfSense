import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { fakeInstallApi } from "@/features/models/local/installs/fake-install-api"
import {
  fakeSpeechRow,
  SPEECH_IN_USE,
} from "@/features/models/local/transcription/fake-speech-rows"
import { render } from "@/test-utils"

import { SpeechSetupPopover } from "./speech-setup-popover"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

type Extra = (path: string, init?: RequestInit) => Response | null

function serving(rows: unknown[], extra: Extra = () => null) {
  const calls: string[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      calls.push(`${init?.method ?? "GET"} ${path}`)
      const handled = extra(path, init)
      if (handled) return handled
      if (path === "/llm/catalog/local") {
        return Response.json({ rows, recommended_id: null })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return calls
}

function renderSetUp({
  onStart,
  onMoreChoices = () => undefined,
}: { onStart?: () => void; onMoreChoices?: () => void } = {}) {
  return render(
    <SpeechSetupPopover
      trigger={<button type="button">Voice input</button>}
      onStart={onStart}
      onMoreChoices={onMoreChoices}
    />
  )
}

async function open() {
  const user = userEvent.setup()
  await user.click(screen.getByRole("button", { name: "Voice input" }))
  const popover = await screen.findByRole("dialog", {
    name: "Set up speech recognition",
  })
  return { user, popover }
}

describe("speech recognition set-up", () => {
  it("asks first, and sends the choice of model to Settings", async () => {
    serving([fakeSpeechRow()])
    const onMoreChoices = vi.fn()
    renderSetUp({ onMoreChoices })
    const { user, popover } = await open()

    expect(popover.textContent).toContain(
      "Turn your voice into text, on this computer. Choose a model in Settings; it downloads once."
    )
    // The models, their downloads and their progress live in Settings alone.
    expect(within(popover).queryByRole("group")).toBeNull()
    await user.click(within(popover).getByRole("button", { name: "Set up…" }))

    expect(onMoreChoices).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("closes on Not now and sets nothing up", async () => {
    const calls = serving([fakeSpeechRow()])
    const onMoreChoices = vi.fn()
    renderSetUp({ onMoreChoices })
    const { user, popover } = await open()

    await user.click(within(popover).getByRole("button", { name: "Not now" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(onMoreChoices).not.toHaveBeenCalled()
    expect(calls.filter((call) => !call.startsWith("GET"))).toEqual([])
  })

  it("says how far a speech download under way has got, and where to watch it", async () => {
    const installs = fakeInstallApi({
      running: [
        {
          id: "job-1",
          catalog_id: "opaque-nemotron",
          label: "Nemotron 3.5 ASR",
          model_types: ["speech_to_text"],
          select: true,
          model_type: "speech_to_text",
          event: {
            type: "downloading",
            message: "Downloading",
            completed: 465_300_000,
            total: 930_600_000,
          },
        },
      ],
    })
    serving([fakeSpeechRow()], installs.handle)
    const onMoreChoices = vi.fn()
    renderSetUp({ onMoreChoices })
    const { user, popover } = await open()

    expect(
      await within(popover).findByText(
        "Downloading the speech recognition model, 50%."
      )
    ).toBeTruthy()
    await user.click(
      within(popover).getByRole("button", { name: "Show progress" })
    )
    expect(onMoreChoices).toHaveBeenCalledOnce()
  })

  it("starts talking once a speech model is in use", async () => {
    serving([fakeSpeechRow({}, SPEECH_IN_USE)])
    const onStart = vi.fn()
    renderSetUp({ onStart })
    const user = userEvent.setup()

    await user.click(screen.getByRole("button", { name: "Voice input" }))
    const popover = await screen.findByRole("dialog", {
      name: "Speech recognition is ready",
    })
    await user.click(
      within(popover).getByRole("button", { name: "Start talking" })
    )

    expect(onStart).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("says it is ready, with nothing to start, where it was opened for a recording", async () => {
    serving([fakeSpeechRow({}, SPEECH_IN_USE)])
    renderSetUp()
    const user = userEvent.setup()

    await user.click(screen.getByRole("button", { name: "Voice input" }))
    const popover = await screen.findByRole("dialog", {
      name: "Speech recognition is ready",
    })

    expect(
      within(popover).queryByRole("button", { name: "Start talking" })
    ).toBeNull()
    await user.click(within(popover).getByRole("button", { name: "Done" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })
})
