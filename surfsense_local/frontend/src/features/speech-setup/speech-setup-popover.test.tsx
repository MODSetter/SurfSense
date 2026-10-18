import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { AppDialogs } from "@/components/ui/app-dialog-slot"
import { EgressPrompt } from "@/features/egress/egress-prompt"
import { fakeInstallApi } from "@/features/models/local/installs/fake-install-api"
import {
  fakeSpeechRow,
  SPEECH_IN_USE,
  SPEECH_INSTALLED,
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
      // A consent records the destinations it switched, not only the route.
      const switched =
        path === "/egress" && init?.method === "PUT"
          ? ` ${JSON.parse(String(init.body)).destinations.join(",")}`
          : ""
      calls.push(`${init?.method ?? "GET"} ${path}${switched}`)
      const handled = extra(path, init)
      if (handled) return handled
      if (path === "/llm/catalog/local") {
        return Response.json({ rows, recommended_id: null })
      }
      if (path === "/llm/selection/speech_to_text" && init?.method === "PUT") {
        return Response.json({
          model_type: "speech_to_text",
          ...JSON.parse(String(init.body)),
          updated_at: "2026-10-14T00:00:00Z",
        })
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
  // As main.tsx mounts them, so a consent asked from inside nests there.
  return render(
    <AppDialogs dialogs={[EgressPrompt]}>
      <SpeechSetupPopover
        trigger={<button type="button">Voice input</button>}
        onStart={onStart}
        onMoreChoices={onMoreChoices}
      />
    </AppDialogs>
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
  it("offers the model with its download and where it works well", async () => {
    serving([fakeSpeechRow()])
    renderSetUp()

    const { popover } = await open()

    expect(popover.textContent).toContain(
      "SurfSense turns your voice into text on this computer. It needs a one-time download."
    )
    const card = await within(popover).findByRole("group", {
      name: "Nemotron 3.5 ASR",
    })
    expect(card.textContent).toContain("931 MB")
    expect(card.textContent).not.toContain("while transcribing")
    // Named in the interface's language, alphabetically.
    expect(
      within(card).getByText(
        "Works well in: Arabic, Bulgarian, Chinese, Croatian, Czech, Danish, Dutch, English, Finnish, French, German, Hindi, Italian, Japanese, Korean, Norwegian Bokmål, Polish, Portuguese, Romanian, Russian, Slovak, Spanish, Swedish, Turkish, Ukrainian, and Vietnamese"
      )
    ).toBeTruthy()
  })

  it("downloads the model and makes it the one in use, showing how far it got", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-nemotron": ["speech_to_text"] },
    })
    serving([fakeSpeechRow()], installs.handle)
    renderSetUp()
    const { user, popover } = await open()

    await user.click(
      await within(popover).findByRole("button", {
        name: "Download and set up",
      })
    )

    await waitFor(() =>
      expect(installs.started).toEqual([
        {
          catalog_id: "opaque-nemotron",
          select: true,
          model_type: "speech_to_text",
        },
      ])
    )
    installs.move({
      type: "downloading",
      message: "Downloading",
      completed: 465_300_000,
      total: 930_600_000,
    })
    expect(await within(popover).findByText("50%")).toBeTruthy()
    expect(
      within(popover).queryByRole("button", { name: "Download and set up" })
    ).toBeNull()
  })

  it("is ready to start talking the moment the download finishes", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-nemotron": ["speech_to_text"] },
    })
    let done = false
    serving([], (path, init) => {
      if (path === "/llm/catalog/local") {
        return Response.json({
          rows: [fakeSpeechRow({}, done ? SPEECH_IN_USE : {})],
          recommended_id: null,
        })
      }
      return installs.handle(path, init)
    })
    renderSetUp({ onStart: () => undefined })
    const { user, popover } = await open()

    await user.click(
      await within(popover).findByRole("button", {
        name: "Download and set up",
      })
    )
    await waitFor(() => expect(installs.started).toHaveLength(1))
    installs.move({ type: "selecting", message: "Selecting" })
    done = true
    installs.complete()

    expect(
      await screen.findByRole("dialog", {
        name: "Speech recognition is ready",
      })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Start talking" })).toBeTruthy()
  })

  it("asks to allow downloads from Hugging Face first, and stays open", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-nemotron": ["speech_to_text"] },
    })
    let allowed = false
    const calls = serving([fakeSpeechRow()], (path, init) => {
      if (path === "/egress" && init?.method === "PUT") {
        allowed = true
        return Response.json([])
      }
      if (path === "/llm/installs" && init?.method === "POST" && !allowed) {
        return Response.json(
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
      }
      return installs.handle(path, init)
    })
    renderSetUp()
    const { user, popover } = await open()

    await user.click(
      await within(popover).findByRole("button", {
        name: "Download and set up",
      })
    )
    await screen.findByRole("alertdialog", {
      name: "Allow searching and downloading models?",
    })
    await user.click(screen.getByRole("button", { name: "Allow" }))

    await waitFor(() =>
      expect(installs.started).toEqual([
        {
          catalog_id: "opaque-nemotron",
          select: true,
          model_type: "speech_to_text",
        },
      ])
    )
    expect(calls).toContain("PUT /egress host:huggingface.co")
    expect(
      screen.getByRole("dialog", { name: "Set up speech recognition" })
    ).toBeTruthy()
  })

  it("uses a model already on disk rather than downloading it again", async () => {
    const calls = serving([fakeSpeechRow({}, SPEECH_INSTALLED)])
    renderSetUp()
    const { user, popover } = await open()

    await user.click(
      await within(popover).findByRole("button", { name: "Set up" })
    )

    await waitFor(() =>
      expect(calls).toContain("PUT /llm/selection/speech_to_text")
    )
    expect(calls).not.toContain("POST /llm/installs")
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

  it("opens Settings for more choices", async () => {
    serving([fakeSpeechRow()])
    const onMoreChoices = vi.fn()
    renderSetUp({ onMoreChoices })
    const { user, popover } = await open()

    await user.click(
      await within(popover).findByRole("button", { name: "More choices" })
    )

    expect(onMoreChoices).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("says so where speech recognition cannot run", async () => {
    serving([])
    renderSetUp()
    const { popover } = await open()

    expect(
      await within(popover).findByText(
        "Speech recognition can’t run on this computer."
      )
    ).toBeTruthy()
    expect(
      within(popover).queryByRole("button", { name: "Download and set up" })
    ).toBeNull()
  })
})
