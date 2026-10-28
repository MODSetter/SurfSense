import { afterAll, afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Toaster, toast } from "sonner"
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type ThreadMessage,
} from "@assistant-ui/react"

import { ChatComposer } from "@/features/chat/chat-composer"
import { QUESTION_MAX_CHARS } from "@/features/chat/question-limit"
import {
  fakeSpeechRow,
  SPEECH_IN_USE,
} from "@/features/models/local/transcription/fake-speech-rows"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

import { fakeMicrophone } from "./capture/fake-microphone"
import { createDictation, type Dictation } from "./dictation-adapter"
import { fakeDictationApi, held, refusal, said } from "./fake-dictation-api"

const MODEL: ModelSelection = {
  model_type: "text_gen",
  provider: "llamacpp",
  connection_id: null,
  name: "Qwen3-1.7B-Q4_K_M",
  updated_at: "2026-09-05T00:00:00Z",
}

function Harness({
  dictation,
  model = MODEL,
  onNew = async () => undefined,
  onOpenSpeechSettings,
}: {
  dictation: Dictation
  model?: ModelSelection | null
  onNew?: () => Promise<void>
  onOpenSpeechSettings?: () => void
}) {
  const runtime = useExternalStoreRuntime<ThreadMessage>({
    messages: [],
    onNew,
    adapters: { dictation },
  })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatComposer
        placement="bottom"
        model={model}
        sourceCount={0}
        isRunning={false}
        providerAvailable
        onModelSetup={() => undefined}
        onModelSelected={() => undefined}
        readsImages={false}
        dictation={dictation}
        onOpenSpeechSettings={onOpenSpeechSettings}
      />
      <Toaster />
    </AssistantRuntimeProvider>
  )
}

function setUp(
  options: Parameters<typeof fakeDictationApi>[0] = {},
  other: (path: string) => Response | null = () => null
) {
  const api = fakeDictationApi(options)
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) =>
        (await api.handle(String(input), init)) ??
        other(String(input)) ??
        Response.json([])
    )
  )
  const mic = fakeMicrophone()
  const dictation = createDictation({ openMicrophone: mic.open })
  const user = userEvent.setup()
  const box = () =>
    screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
  const listening = () => waitFor(() => expect(mic.state.open).toBe(true))
  return { api, mic, dictation, user, box, listening }
}

const startButton = () =>
  screen.findByRole("button", { name: "Start voice input" })

afterEach(() => {
  // Sonner keeps its toasts across tests; one left over would show in the next Toaster.
  toast.dismiss()
  cleanup()
  vi.unstubAllGlobals()
})

// A dismissed toast leaves 200 ms later (sonner's TIME_BEFORE_UNMOUNT); fired after the
// file ends, that removal finds no window and fails the run.
afterAll(() => new Promise((resolve) => setTimeout(resolve, 300)))

/** The composer's footer line, which a problem never replaces. */
const disclaimerStays = () =>
  expect(
    screen.getByText("SurfSense can make mistakes. Check important answers.")
  ).toBeTruthy()

describe("voice input in the composer", () => {
  it("listens on a click and puts each phrase in the box as it lands", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Hello there."), said("How are you?"))
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    // Starting: a spinner in the mic's place, and nothing else yet.
    const starting = screen.getByRole("button", {
      name: "Starting the microphone…",
    })
    expect(starting.hasAttribute("disabled")).toBe(true)
    expect(screen.queryByText("0:00")).toBeNull()
    expect(screen.queryByRole("button", { name: "Stop and insert" })).toBeNull()
    expect(screen.getByRole("button", { name: "Send message" })).toBeTruthy()
    await listening()
    act(() => mic.say())

    await waitFor(() => expect(box().value).toBe("Hello there."))
    expect(box().readOnly).toBe(true)
    expect(screen.getByRole("status").textContent).toBe("Listening")
    expect(screen.getByText("0:00")).toBeTruthy()
    // The recording takes the mic's and Send's places, never the line below.
    expect(
      screen.queryByRole("button", { name: "Start voice input" })
    ).toBeNull()
    expect(screen.queryByRole("button", { name: "Send message" })).toBeNull()
    expect(screen.getByRole("button", { name: "Stop and insert" })).toBeTruthy()
    disclaimerStays()
    act(() => mic.say())
    await waitFor(() => expect(box().value).toBe("Hello there. How are you?"))
  })

  it("on Enter, stops, waits for the last phrase and inserts it, sending nothing", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    const last = held(() => Response.json(said("Second.")))
    api.answer(said("First."), last.answer)
    const onNew = vi.fn(async () => undefined)
    render(<Harness dictation={dictation} onNew={onNew} />)

    await user.click(await startButton())
    await listening()
    act(() => mic.say())
    await waitFor(() => expect(box().value).toBe("First."))
    act(() => mic.speak(0.8))
    await user.type(box(), "{Enter}")

    expect(mic.state.open).toBe(false)
    expect(await screen.findByText("Transcribing…")).toBeTruthy()
    last.release()
    await waitFor(() => expect(box().value).toBe("First. Second."))
    await waitFor(() => expect(box().readOnly).toBe(false))
    expect(onNew).not.toHaveBeenCalled()
  })

  it("stops and inserts from the button in Send's place, sending nothing", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Draft question."), said("More."))
    const onNew = vi.fn(async () => undefined)
    render(<Harness dictation={dictation} onNew={onNew} />)

    await user.click(await startButton())
    await listening()
    act(() => mic.say())
    await waitFor(() => expect(box().value).toBe("Draft question."))
    act(() => mic.speak(0.8))
    await user.click(screen.getByRole("button", { name: "Stop and insert" }))

    await waitFor(() => expect(box().value).toBe("Draft question. More."))
    await waitFor(() => expect(box().readOnly).toBe(false))
    expect(onNew).not.toHaveBeenCalled()
    // Send comes back, ready to send what was said.
    expect(screen.getByRole("button", { name: "Send message" })).toBeTruthy()
  })

  it("on Escape, drops the recording and puts back the text from before the mic", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Never mind."))
    render(<Harness dictation={dictation} />)
    await user.type(box(), "Before")

    await user.click(await startButton())
    await listening()
    act(() => mic.say())
    await waitFor(() => expect(box().value).toBe("Before Never mind."))
    await user.type(box(), "{Escape}")

    expect(box().value).toBe("Before")
    expect(mic.state.open).toBe(false)
    expect(box().readOnly).toBe(false)
    expect(await startButton()).toBeTruthy()
  })

  it("keeps listening after a long press: there is no push to talk", async () => {
    const { mic, dictation, user } = setUp()
    render(<Harness dictation={dictation} />)
    const button = await startButton()

    // Held past the old push-to-talk threshold, then let go: a plain click.
    await user.pointer({ keys: "[MouseLeft>]", target: button })
    await new Promise((resolve) => setTimeout(resolve, 320))
    await user.pointer({ keys: "[/MouseLeft]", target: button })

    await waitFor(() => expect(mic.state.open).toBe(true))
    // Stop and insert comes with the first real sound.
    act(() => mic.speak(0.2))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(mic.state.open).toBe(true)
    expect(screen.getByRole("button", { name: "Stop and insert" })).toBeTruthy()
  })

  it("starts with Enter on the focused mic, then stops with Enter in the message box", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("By keyboard."))
    render(<Harness dictation={dictation} />)

    ;(await startButton()).focus()
    await user.keyboard("{Enter}")
    await listening()
    // The mic hides, so the focus moves to the message box rather than nowhere.
    expect(document.activeElement).toBe(box())
    act(() => mic.speak(1.2))
    await user.keyboard("{Enter}")

    await waitFor(() => expect(box().value).toBe("By keyboard."))
    expect(mic.state.open).toBe(false)
  })

  it("sets up speech recognition in Settings when no model is chosen", async () => {
    const { dictation, user, mic } = setUp({
      status: { ready: false, reason: "needs_speech_model", model: null },
    })
    const onOpenSpeechSettings = vi.fn()
    render(
      <Harness
        dictation={dictation}
        onOpenSpeechSettings={onOpenSpeechSettings}
      />
    )

    await user.click(
      await screen.findByRole("button", { name: "Set up voice input" })
    )

    const popover = await screen.findByRole("dialog", {
      name: "Set up speech recognition",
    })
    await user.click(within(popover).getByRole("button", { name: "Set up…" }))
    expect(onOpenSpeechSettings).toHaveBeenCalledOnce()
    expect(mic.state.opens).toBe(0)
  })

  it("starts talking from the set-up once a speech model is in use", async () => {
    const { api, dictation, user, mic, box, listening } = setUp(
      { status: { ready: false, reason: "needs_speech_model", model: null } },
      (path) =>
        path === "/llm/catalog/local"
          ? Response.json({
              rows: [fakeSpeechRow({}, SPEECH_IN_USE)],
              recommended_id: null,
            })
          : null
    )
    api.answer(said("Set up and talking."))
    render(<Harness dictation={dictation} />)

    await user.click(
      await screen.findByRole("button", { name: "Set up voice input" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Start talking" })
    )
    await listening()
    act(() => mic.say())

    await waitFor(() => expect(box().value).toBe("Set up and talking."))
    expect(screen.getByRole("button", { name: "Stop and insert" })).toBeTruthy()
  })

  it("is off whenever the message box is, and at the message limit", async () => {
    const { dictation, user, box } = setUp()
    const { rerender } = render(<Harness dictation={dictation} model={null} />)
    expect((await startButton()).hasAttribute("disabled")).toBe(true)

    rerender(<Harness dictation={dictation} />)
    expect((await startButton()).hasAttribute("disabled")).toBe(false)
    await user.click(box())
    await user.paste("x".repeat(QUESTION_MAX_CHARS))

    expect((await startButton()).hasAttribute("disabled")).toBe(true)
  })

  it("says the microphone is off, and opens the system’s settings", async () => {
    const openSettings = vi.fn(async () => true)
    const { mic, dictation, user } = setUp()
    vi.stubGlobal("surfsense", {
      apiUrl: "",
      platform: "win32",
      microphone: {
        status: async () => "denied",
        request: async () => "denied",
        openSettings,
      },
    })
    mic.refuse(new DOMException("Permission denied", "NotAllowedError"))
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())

    expect(
      await screen.findByText("Microphone access is off for SurfSense.")
    ).toBeTruthy()
    disclaimerStays()
    await user.click(screen.getByRole("button", { name: "Open settings" }))
    expect(openSettings).toHaveBeenCalledOnce()
  })

  it("says the microphone needs HTTPS on a page the browser keeps it from", async () => {
    // Another device than the Docker host, over plain HTTP: no mediaDevices at all.
    vi.stubGlobal("isSecureContext", false)
    const { mic, dictation, user } = setUp()
    mic.refuse(new TypeError("navigator.mediaDevices is undefined"))
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    const https =
      "Your browser allows the microphone only over HTTPS, or on the computer running SurfSense."

    // It stays true until the page changes, so it is no passing toast.
    // The click left the pointer on the mic: off and back on, as a reader would.
    await user.unhover(await startButton())
    await user.hover(await startButton())
    expect((await screen.findByRole("tooltip")).textContent).toBe(https)
    expect(screen.queryAllByText(https)).toHaveLength(1)
    disclaimerStays()
  })

  it("says on the mic, not in a toast, that no microphone was found", async () => {
    const { mic, dictation, user } = setUp()
    mic.refuse(new DOMException("", "NotFoundError"))
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    // The click left the pointer on the mic: off and back on, as a reader would.
    await user.unhover(await startButton())
    await user.hover(await startButton())

    expect((await screen.findByRole("tooltip")).textContent).toBe(
      "No microphone found."
    )
    expect(screen.queryAllByText("No microphone found.")).toHaveLength(1)
  })

  it("keeps a phrase it could not transcribe, and Retry puts it in the box", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Got this."), () =>
      Response.json({ detail: [{ msg: "bad audio" }] }, { status: 422 })
    )
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    await listening()
    act(() => mic.say())
    act(() => mic.say())

    expect(
      await screen.findByText("Couldn’t turn part of your speech into text.")
    ).toBeTruthy()
    disclaimerStays()
    expect(box().value).toBe("Got this.")
    api.answer(said("And this."))
    await user.click(screen.getByRole("button", { name: "Retry" }))

    await waitFor(() => expect(box().value).toBe("Got this. And this."))
    await waitFor(() =>
      expect(
        screen.queryByText("Couldn’t turn part of your speech into text.")
      ).toBeNull()
    )
  })

  it("names both sizes when memory is short", async () => {
    const { dictation, user } = setUp({
      open: () =>
        refusal(409, "transcription_needs_memory", {
          needed_bytes: 2_900_000_000,
          available_bytes: 1_200_000_000,
        }),
    })
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())

    expect(
      await screen.findByText(
        "Transcribing needs about 2.9 GB free; this computer has 1.2 GB."
      )
    ).toBeTruthy()
    disclaimerStays()
  })

  it("names both sizes when a phrase is refused for memory, and offers Retry", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(() =>
      refusal(409, "transcription_needs_memory", {
        needed_bytes: 2_900_000_000,
        available_bytes: 1_200_000_000,
      })
    )
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    await listening()
    act(() => mic.say())

    expect(
      await screen.findByText(
        "Transcribing needs about 2.9 GB free; this computer has 1.2 GB."
      )
    ).toBeTruthy()
    api.answer(said("Freed up."))
    await user.click(screen.getByRole("button", { name: "Retry" }))

    await waitFor(() => expect(box().value).toBe("Freed up."))
  })

  it("says why it stopped at the message limit", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("one two three four five"))
    render(<Harness dictation={dictation} />)
    await user.click(box())
    await user.paste("x".repeat(QUESTION_MAX_CHARS - 10))

    await user.click(await startButton())
    await listening()
    act(() => mic.say())

    expect(
      await screen.findByText(
        "Voice input stopped at the 4,096-character message limit."
      )
    ).toBeTruthy()
    disclaimerStays()
    expect(box().value).toBe(`${"x".repeat(QUESTION_MAX_CHARS - 10)} one two`)
  })
})
