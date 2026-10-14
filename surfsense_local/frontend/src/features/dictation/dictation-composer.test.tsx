import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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
  cleanup()
  vi.unstubAllGlobals()
})

describe("voice input in the composer", () => {
  it("listens on a click and puts each phrase in the box as it lands", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Hello there."), said("How are you?"))
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    expect(screen.getByRole("status").textContent).toBe(
      "Starting the microphone…"
    )
    await listening()
    act(() => mic.say())

    await waitFor(() => expect(box().value).toBe("Hello there."))
    expect(box().readOnly).toBe(true)
    expect(screen.getByRole("status").textContent).toBe("Listening")
    expect(screen.getByText("0:00")).toBeTruthy()
    expect(
      screen
        .getByRole("button", { name: "Stop voice input" })
        .getAttribute("aria-pressed")
    ).toBe("true")
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

  it("on Send, stops and inserts instead of sending", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Draft question."), said("More."))
    const onNew = vi.fn(async () => undefined)
    render(<Harness dictation={dictation} onNew={onNew} />)

    await user.click(await startButton())
    await listening()
    act(() => mic.say())
    await waitFor(() => expect(box().value).toBe("Draft question."))
    act(() => mic.speak(0.8))
    await user.click(screen.getByRole("button", { name: "Send message" }))

    await waitFor(() => expect(box().value).toBe("Draft question. More."))
    await waitFor(() => expect(box().readOnly).toBe(false))
    expect(onNew).not.toHaveBeenCalled()
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

  it("stops on a second click and keeps the text", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Keep this."))
    render(<Harness dictation={dictation} />)

    await user.click(await startButton())
    await listening()
    act(() => mic.speak(1.2))
    await user.click(screen.getByRole("button", { name: "Stop voice input" }))

    await waitFor(() => expect(box().value).toBe("Keep this."))
    expect(mic.state.open).toBe(false)
    expect(await startButton()).toBeTruthy()
  })

  it("listens while the mic is held, and stops on release", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("Push to talk."))
    render(<Harness dictation={dictation} />)
    const button = await startButton()

    await user.pointer({ keys: "[MouseLeft>]", target: button })
    await listening()
    act(() => mic.speak(1.2))
    await new Promise((resolve) => setTimeout(resolve, 320))
    await user.pointer({ keys: "[/MouseLeft]", target: button })

    expect(mic.state.open).toBe(false)
    await waitFor(() => expect(box().value).toBe("Push to talk."))
  })

  it("toggles with Enter on the focused mic", async () => {
    const { api, mic, dictation, user, box, listening } = setUp()
    api.answer(said("By keyboard."))
    render(<Harness dictation={dictation} />)

    ;(await startButton()).focus()
    await user.keyboard("{Enter}")
    await listening()
    act(() => mic.speak(1.2))
    await user.keyboard("{Enter}")

    await waitFor(() => expect(box().value).toBe("By keyboard."))
    expect(mic.state.open).toBe(false)
  })

  it("sets up speech recognition instead when no model is chosen", async () => {
    const { dictation, user, mic } = setUp({
      status: { ready: false, reason: "needs_speech_model", model: null },
    })
    render(<Harness dictation={dictation} />)

    await user.click(
      await screen.findByRole("button", { name: "Set up voice input" })
    )

    expect(
      await screen.findByRole("dialog", { name: "Set up speech recognition" })
    ).toBeTruthy()
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
    expect(
      screen.getByRole("button", { name: "Stop voice input" })
    ).toBeTruthy()
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

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Microphone access is off for SurfSense."
    )
    await user.click(screen.getByRole("button", { name: "Open settings" }))
    expect(openSettings).toHaveBeenCalledOnce()
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

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Couldn’t turn part of your speech into text."
    )
    expect(box().value).toBe("Got this.")
    api.answer(said("And this."))
    await user.click(screen.getByRole("button", { name: "Retry" }))

    await waitFor(() => expect(box().value).toBe("Got this. And this."))
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull())
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

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Transcribing needs about 2.9 GB free; this computer has 1.2 GB."
    )
    await user.click(screen.getByRole("button", { name: "Dismiss" }))
    expect(screen.queryByRole("alert")).toBeNull()
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

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Transcribing needs about 2.9 GB free; this computer has 1.2 GB."
    )
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

    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toBe(
        "Voice input stopped at the 4,096-character message limit."
      )
    )
    expect(box().value).toBe(`${"x".repeat(QUESTION_MAX_CHARS - 10)} one two`)
  })
})
