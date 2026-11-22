import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"

import { openDictationSession } from "./dictation-session"
import { fakeDictationApi, held, refusal, said } from "./fake-dictation-api"

const wav = (label: string) => new Blob([label], { type: "audio/wav" })

function serve(api: ReturnType<typeof fakeDictationApi>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) =>
        (await api.handle(String(input), init)) ??
        Response.json({ detail: "not found" }, { status: 404 })
    )
  )
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("the dictation session", () => {
  it("opens a session and says whether the model is already loaded", async () => {
    const api = fakeDictationApi({ warm: "loading" })
    serve(api)

    const session = await openDictationSession({ onEnded: () => undefined })

    expect(session.warm).toBe("loading")
    expect(api.calls).toEqual(["POST /llm/transcription/dictations"])
    session.end()
  })

  it("sends one phrase at a time, in the order they were spoken", async () => {
    const api = fakeDictationApi()
    const first = held(() => Response.json(said("Hello there.")))
    api.answer(first.answer, said("How are you?"))
    serve(api)
    const session = await openDictationSession({ onEnded: () => undefined })

    const one = session.transcribe(wav("one"))
    const two = session.transcribe(wav("two"))
    await vi.advanceTimersByTimeAsync(0)
    expect(api.phrases).toHaveLength(1)

    first.release()
    expect((await one).text).toBe("Hello there.")
    expect((await two).text).toBe("How are you?")
    expect(await api.phrases[1].text()).toBe("two")
    session.end()
  })

  it("asks once more, 2 s later, while the server restarts", async () => {
    const api = fakeDictationApi()
    api.answer(
      () => refusal(503, "transcription_unavailable"),
      said("Still here.")
    )
    serve(api)
    const session = await openDictationSession({ onEnded: () => undefined })

    const phrase = session.transcribe(wav("one"))
    await vi.advanceTimersByTimeAsync(1_999)
    expect(api.phrases).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)

    expect((await phrase).text).toBe("Still here.")
    expect(api.phrases).toHaveLength(2)
    session.end()
  })

  it("gives a phrase up when the second try fails too, and goes on with the next", async () => {
    const api = fakeDictationApi()
    api.answer(
      () => refusal(503, "transcription_unavailable"),
      () => refusal(503, "transcription_unavailable"),
      said("Next one.")
    )
    serve(api)
    const session = await openDictationSession({ onEnded: () => undefined })

    const failed = session.transcribe(wav("one"))
    const next = session.transcribe(wav("two"))
    const outcome = failed.catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(2_000)

    const error = await outcome
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe("transcription_unavailable")
    expect((await next).text).toBe("Next one.")
    session.end()
  })

  it("does not ask again for a phrase the server refused for itself", async () => {
    const api = fakeDictationApi()
    api.answer(() => refusal(409, "needs_speech_model"))
    serve(api)
    const session = await openDictationSession({ onEnded: () => undefined })

    const outcome = session
      .transcribe(wav("one"))
      .catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(5_000)

    expect(((await outcome) as ApiError).code).toBe("needs_speech_model")
    expect(api.phrases).toHaveLength(1)
    session.end()
  })

  it("keeps itself alive every 10 s until it ends, then says so once", async () => {
    const api = fakeDictationApi()
    serve(api)
    const session = await openDictationSession({ onEnded: () => undefined })

    await vi.advanceTimersByTimeAsync(25_000)
    session.end()
    session.end()
    await vi.advanceTimersByTimeAsync(30_000)

    expect(api.calls).toEqual([
      "POST /llm/transcription/dictations",
      "POST /llm/transcription/dictations/d1/keepalive",
      "POST /llm/transcription/dictations/d1/keepalive",
      "DELETE /llm/transcription/dictations/d1",
    ])
  })

  it("tells its owner when the API no longer knows it", async () => {
    const api = fakeDictationApi()
    serve(api)
    vi.mocked(fetch).mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) =>
        String(input).endsWith("/keepalive")
          ? refusal(404, "dictation_ended")
          : ((await api.handle(String(input), init)) as Response)
    )
    const onEnded = vi.fn()
    await openDictationSession({ onEnded })

    await vi.advanceTimersByTimeAsync(10_000)

    expect(onEnded).toHaveBeenCalledOnce()
  })
})
