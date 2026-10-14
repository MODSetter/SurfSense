import { afterEach, describe, expect, it, vi } from "vitest"
import { renderHook } from "@testing-library/react"
import {
  useExternalStoreRuntime,
  type ThreadMessage,
} from "@assistant-ui/react"

import { QUESTION_MAX_CHARS } from "@/features/chat/question-limit"

import { fakeMicrophone } from "./capture/fake-microphone"
import { createDictation } from "./dictation-adapter"
import { fakeDictationApi, held, refusal, said } from "./fake-dictation-api"

function setUp(options: Parameters<typeof fakeDictationApi>[0] = {}) {
  const api = fakeDictationApi(options)
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) =>
        (await api.handle(String(input), init)) ??
        Response.json({ detail: "not found" }, { status: 404 })
    )
  )
  const mic = fakeMicrophone()
  const dictation = createDictation({ openMicrophone: mic.open })
  const { result } = renderHook(() =>
    useExternalStoreRuntime<ThreadMessage>({
      messages: [],
      onNew: async () => undefined,
      adapters: { dictation },
    })
  )
  const composer = result.current.thread.composer
  const text = () => composer.getState().text
  const listening = () => vi.waitFor(() => expect(mic.state.open).toBe(true))
  return { api, mic, dictation, composer, text, listening }
}

async function header(wav: Blob) {
  const view = new DataView(await wav.arrayBuffer())
  return {
    channels: view.getUint16(22, true),
    sampleRate: view.getUint32(24, true),
    bits: view.getUint16(34, true),
  }
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("dictation", () => {
  it("is starting until the first real frame, then running", async () => {
    const { dictation, mic } = setUp()
    const started = vi.fn()

    const session = dictation.listen()
    session.onSpeechStart(started)
    expect(session.status.type).toBe("starting")
    await vi.waitFor(() => expect(mic.state.open).toBe(true))
    expect(session.status.type).toBe("starting")
    expect(dictation.getView().phase).toBe("arming")

    mic.quiet(0.02)

    expect(session.status.type).toBe("running")
    expect(started).toHaveBeenCalledOnce()
    expect(dictation.getView().phase).toBe("listening")
    session.cancel()
  })

  it("puts each phrase in the box as it lands, all of it so far", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(said("Hello there."), said("How are you?"))
    composer.setText("Note:")

    dictation.start(composer)
    await listening()
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("Note: Hello there."))
    mic.say()

    await vi.waitFor(() =>
      expect(text()).toBe("Note: Hello there. How are you?")
    )
    expect(composer.getState().dictation).toBeDefined()
    dictation.cancel()
  })

  it("sends each phrase as a 16 kHz mono 16-bit WAV", async () => {
    const { api, mic, dictation, composer, listening } = setUp()
    api.answer(said("Hello."))

    dictation.start(composer)
    await listening()
    mic.say()

    await vi.waitFor(() => expect(api.phrases).toHaveLength(1))
    expect(await header(api.phrases[0])).toEqual({
      channels: 1,
      sampleRate: 16_000,
      bits: 16,
    })
    dictation.cancel()
  })

  it("on stop, waits for the last phrase and hands over one final result before it ends", async () => {
    const { api, mic, dictation, listening } = setUp()
    const last = held(() => Response.json(said("Fine, thanks.")))
    api.answer(said("How are you?"), last.answer)
    const heard: string[] = []

    const session = dictation.listen()
    session.onSpeech(({ transcript, isFinal }) =>
      heard.push(
        `${isFinal ? "final" : "interim"}:${transcript}:${session.status.type}`
      )
    )
    await listening()
    mic.say()
    await vi.waitFor(() => expect(heard).toHaveLength(1))
    mic.speak(0.6)

    const stopped = session.stop()
    expect(mic.state.open).toBe(false)
    expect(dictation.getView().phase).toBe("finishing")
    last.release()
    await stopped

    expect(heard).toEqual([
      "interim:How are you?:running",
      "interim:How are you? Fine, thanks.:running",
      "final:How are you? Fine, thanks.:running",
    ])
    expect(session.status).toEqual({ type: "ended", reason: "stopped" })
    expect(dictation.getView().phase).toBe("idle")
    await vi.waitFor(() =>
      expect(api.calls).toContain("DELETE /llm/transcription/dictations/d1")
    )
  })

  it("lands the last phrase in the box when stopped through the runtime", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(said("One."), said("Two."))

    dictation.start(composer)
    await listening()
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("One."))
    mic.speak(0.8)
    dictation.stop()

    await vi.waitFor(() =>
      expect(composer.getState().dictation).toBeUndefined()
    )
    expect(text()).toBe("One. Two.")
  })

  it("inserts nothing when nothing was said", async () => {
    const { mic, dictation, composer, text, listening } = setUp()
    composer.setText("Draft")

    dictation.start(composer)
    await listening()
    mic.quiet(1)
    dictation.stop()

    await vi.waitFor(() =>
      expect(composer.getState().dictation).toBeUndefined()
    )
    expect(text()).toBe("Draft")
  })

  it("joins Chinese and Japanese phrases with no space, and others with one", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(
      said("你好。", "zh"),
      said("今天天气很好。", "zh"),
      said("ありがとう。", "ja"),
      said("OK, thanks.", "en")
    )

    dictation.start(composer)
    await listening()
    for (let i = 0; i < 4; i++) mic.say()

    await vi.waitFor(() =>
      expect(text()).toBe("你好。今天天气很好。ありがとう。 OK, thanks.")
    )
    dictation.cancel()
  })

  it("joins Chinese phrases with no space when no language came back with them", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(said("你好。", null), said("「谢谢」", null), said("OK.", null))

    dictation.start(composer)
    await listening()
    for (let i = 0; i < 3; i++) mic.say()

    await vi.waitFor(() => expect(text()).toBe("你好。「谢谢」 OK."))
    dictation.cancel()
  })

  it("stops at the message limit, cut at the last whole word", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    // Room for 20 characters after the separating space.
    const before = "x".repeat(QUESTION_MAX_CHARS - 21)
    composer.setText(before)
    api.answer(said("Seven words fit here and then"), said("never sent"))

    dictation.start(composer)
    await listening()
    mic.say()

    await vi.waitFor(() =>
      expect(dictation.getView()).toEqual({
        phase: "problem",
        problem: { kind: "at_limit" },
        canRetry: false,
      })
    )
    expect(text()).toBe(`${before} Seven words fit here`)
    expect(text().length).toBeLessThanOrEqual(QUESTION_MAX_CHARS)
    expect(mic.state.open).toBe(false)
    mic.say()
    expect(api.phrases).toHaveLength(1)
  })

  it("cuts Japanese at the limit by the character", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    const before = "x".repeat(QUESTION_MAX_CHARS - 6)
    composer.setText(before)
    api.answer(said("今日はとても良い天気です。", "ja"))

    dictation.start(composer)
    await listening()
    mic.say()

    await vi.waitFor(() => expect(text()).toBe(`${before} 今日はとて`))
  })

  it("on cancel, drops what was not transcribed and lands nothing later", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    const late = held(() => Response.json(said("Too late.")))
    api.answer(said("Kept?"), late.answer)
    composer.setText("Before")

    dictation.start(composer)
    await listening()
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("Before Kept?"))
    mic.say()
    await vi.waitFor(() => expect(api.phrases).toHaveLength(2))

    dictation.cancel(composer)
    late.release()

    expect(mic.state.open).toBe(false)
    expect(text()).toBe("Before")
    expect(dictation.getView().phase).toBe("idle")
    await vi.waitFor(() =>
      expect(api.calls).toContain("DELETE /llm/transcription/dictations/d1")
    )
    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(text()).toBe("Before")
  })

  it("keeps a phrase that failed twice, and Retry lands it", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "setInterval", "Date"] })
    const { api, mic, dictation, composer, text } = setUp()
    api.answer(
      said("First part."),
      () => refusal(503, "transcription_unavailable"),
      () => refusal(503, "transcription_unavailable")
    )

    dictation.start(composer)
    await vi.waitFor(() => expect(mic.state.open).toBe(true))
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("First part."))
    mic.say()
    await vi.advanceTimersByTimeAsync(2_000)

    await vi.waitFor(() =>
      expect(dictation.getView()).toEqual({
        phase: "problem",
        problem: { kind: "phrase_failed" },
        canRetry: true,
      })
    )
    expect(mic.state.open).toBe(false)
    expect(text()).toBe("First part.")

    api.answer(said("Second part."))
    dictation.retry(composer)

    await vi.waitFor(() => expect(text()).toBe("First part. Second part."))
    await vi.waitFor(() => expect(dictation.getView().phase).toBe("idle"))
    expect(mic.state.opens).toBe(1)
  })

  it("says memory is short when a phrase is refused for it, keeping the audio for Retry", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(said("Before the podcast."), () =>
      refusal(409, "transcription_needs_memory", {
        needed_bytes: 2_900_000_000,
        available_bytes: 1_200_000_000,
      })
    )

    dictation.start(composer)
    await listening()
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("Before the podcast."))
    mic.say()

    await vi.waitFor(() =>
      expect(dictation.getView()).toEqual({
        phase: "problem",
        problem: {
          kind: "transcription_needs_memory",
          neededBytes: 2_900_000_000,
          availableBytes: 1_200_000_000,
          message: "Refused: transcription_needs_memory",
        },
        canRetry: true,
      })
    )
    expect(api.phrases).toHaveLength(2)
    expect(mic.state.open).toBe(false)

    api.answer(said("After it."))
    dictation.retry(composer)

    await vi.waitFor(() => expect(text()).toBe("Before the podcast. After it."))
    await vi.waitFor(() => expect(dictation.getView().phase).toBe("idle"))
  })

  it("keeps the audio when a Retry is refused for memory, and offers Retry again", async () => {
    const { api, mic, dictation, composer, listening } = setUp()
    api.answer(() => refusal(422, "unfit_audio"))
    dictation.start(composer)
    await listening()
    mic.say()
    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({ canRetry: true })
    )
    const served = vi.mocked(fetch).getMockImplementation()!
    vi.mocked(fetch).mockImplementation(async (input, init) =>
      String(input) === "/llm/transcription/dictations"
        ? refusal(409, "transcription_needs_memory", {
            needed_bytes: 2_900_000_000,
            available_bytes: 1_200_000_000,
          })
        : served(input, init)
    )

    dictation.retry(composer)

    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({
        phase: "problem",
        problem: { kind: "transcription_needs_memory" },
        canRetry: true,
      })
    )
    expect(api.phrases).toHaveLength(1)
  })

  it("says why when the microphone is refused, and lets the API go", async () => {
    const { api, mic, dictation, composer, text } = setUp()
    mic.refuse(new DOMException("Permission denied", "NotAllowedError"))
    composer.setText("Draft")

    dictation.start(composer)

    await vi.waitFor(() =>
      expect(dictation.getView()).toEqual({
        phase: "problem",
        problem: { kind: "microphone_off" },
        canRetry: false,
      })
    )
    await vi.waitFor(() =>
      expect(api.calls).toContain("DELETE /llm/transcription/dictations/d1")
    )
    expect(text()).toBe("Draft")
  })

  it.each([
    ["NotFoundError", "no_microphone"],
    ["NotReadableError", "microphone_busy"],
  ])("names a %s as %s", async (name, kind) => {
    const { mic, dictation, composer } = setUp()
    mic.refuse(new DOMException("", name))

    dictation.start(composer)

    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({ problem: { kind } })
    )
  })

  it("is refused at once when memory is short, before anyone speaks", async () => {
    const { mic, dictation, composer } = setUp({
      open: () =>
        refusal(409, "transcription_needs_memory", {
          needed_bytes: 2_900_000_000,
          available_bytes: 1_200_000_000,
        }),
    })

    dictation.start(composer)

    await vi.waitFor(() =>
      expect(dictation.getView()).toEqual({
        phase: "problem",
        problem: {
          kind: "transcription_needs_memory",
          neededBytes: 2_900_000_000,
          availableBytes: 1_200_000_000,
          message: "Refused: transcription_needs_memory",
        },
        canRetry: false,
      })
    )
    await vi.waitFor(() =>
      expect(mic.state).toMatchObject({ opens: 1, open: false })
    )
  })

  it("keeps what was said when the microphone is unplugged", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(said("Before the cable."), said("Last words."))

    dictation.start(composer)
    await listening()
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("Before the cable."))
    mic.speak(0.6)
    mic.unplug()

    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({
        problem: { kind: "microphone_disconnected" },
      })
    )
    expect(text()).toBe("Before the cable. Last words.")
  })

  it("stops, keeping the text, when the API no longer knows the session", async () => {
    const { api, mic, dictation, composer, text, listening } = setUp()
    api.answer(said("Saved."), () => refusal(404, "dictation_ended"))

    dictation.start(composer)
    await listening()
    mic.say()
    mic.say()

    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({
        problem: { kind: "dictation_ended" },
      })
    )
    expect(text()).toBe("Saved.")
    expect(mic.state.open).toBe(false)
  })

  it("stops when the speech model was removed mid-recording", async () => {
    const { api, mic, dictation, composer, listening } = setUp()
    api.answer(() => refusal(409, "needs_speech_model"))

    dictation.start(composer)
    await listening()
    mic.say()

    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({
        problem: { kind: "model_removed" },
      })
    )
  })

  it("warns at 4:30 and stops at 5:00, keeping the text", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "setInterval", "Date"] })
    const { api, mic, dictation, composer, text } = setUp()
    api.answer(said("A long thought."))

    dictation.start(composer)
    await vi.waitFor(() => expect(mic.state.open).toBe(true))
    mic.say()
    await vi.waitFor(() => expect(text()).toBe("A long thought."))

    await vi.advanceTimersByTimeAsync(269_000)
    expect(dictation.getView()).toMatchObject({ warning: false })
    await vi.advanceTimersByTimeAsync(1_000)
    expect(dictation.getView()).toMatchObject({
      phase: "listening",
      warning: true,
    })
    await vi.advanceTimersByTimeAsync(30_000)

    await vi.waitFor(() =>
      expect(dictation.getView()).toMatchObject({
        problem: { kind: "time_limit" },
      })
    )
    expect(mic.state.open).toBe(false)
    expect(text()).toBe("A long thought.")
  })

  it("says the model is loading only once a phrase has waited 2 s for it", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "setInterval", "Date"] })
    const { api, mic, dictation, composer, text } = setUp({ warm: "loading" })
    const first = held(() => Response.json(said("Loaded.")))
    api.answer(first.answer)

    dictation.start(composer)
    await vi.waitFor(() => expect(mic.state.open).toBe(true))
    mic.say()
    await vi.advanceTimersByTimeAsync(1_900)
    expect(dictation.getView()).toMatchObject({ loading: false })
    await vi.advanceTimersByTimeAsync(100)
    expect(dictation.getView()).toMatchObject({ loading: true })

    first.release()
    await vi.waitFor(() => expect(text()).toBe("Loaded."))
    expect(dictation.getView()).toMatchObject({ loading: false })
    dictation.cancel()
  })
})
