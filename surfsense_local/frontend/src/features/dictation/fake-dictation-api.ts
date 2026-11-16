import type { PhraseText, TranscriptionStatus } from "./api"

const READY: TranscriptionStatus = {
  ready: true,
  reason: null,
  model: "nemotron-3.5-asr-streaming-0.6b-q8_0",
  language_intent: "auto",
  languages: ["en", "ja", "zh"],
}

/** What one phrase upload answers: a result, or a response made when asked. */
export type PhraseAnswer = PhraseText | (() => Response | Promise<Response>)

/** The API's refusal, in the app's `{detail: {message, code, …}}` shape. */
export function refusal(
  status: number,
  code: string,
  extra: Record<string, unknown> = {}
): Response {
  return Response.json(
    { detail: { message: `Refused: ${code}`, code, ...extra } },
    { status }
  )
}

/**
 * Stands in for the transcription routes, so a test can say what each phrase
 * comes back as, and see what the composer sent. Shared by every dictation test.
 */
export function fakeDictationApi({
  status = READY,
  warm = "loaded",
  open,
}: {
  status?: Partial<TranscriptionStatus>
  warm?: "loaded" | "loading"
  /** In place of a session: a refusal, say. */
  open?: () => Response
} = {}) {
  const calls: string[] = []
  const phrases: Blob[] = []
  const answers: PhraseAnswer[] = []
  let current: TranscriptionStatus = { ...READY, ...status }
  let opened = 0

  const handle = (
    path: string,
    init?: RequestInit
  ): Response | Promise<Response> | null => {
    if (!path.startsWith("/llm/transcription/")) return null
    const method = init?.method ?? "GET"
    calls.push(`${method} ${path}`)
    if (path === "/llm/transcription/status") return Response.json(current)
    if (path === "/llm/transcription/dictations" && method === "POST") {
      if (open) return open()
      opened += 1
      return Response.json({ id: `d${opened}`, warm }, { status: 201 })
    }
    if (method === "POST" && path.endsWith("/phrases")) {
      phrases.push((init?.body as FormData).get("audio") as Blob)
      const answer = answers.shift() ?? {
        text: "",
        language: null,
        no_speech: true,
      }
      return typeof answer === "function" ? answer() : Response.json(answer)
    }
    if (
      (method === "POST" && path.endsWith("/keepalive")) ||
      method === "DELETE"
    ) {
      return new Response(null, { status: 204 })
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  }

  return {
    handle,
    calls,
    /** Every phrase the composer sent, as the WAV it uploaded. */
    phrases,
    /** What the next phrases come back as, in order. */
    answer: (...next: PhraseAnswer[]) => {
      answers.push(...next)
    },
    setStatus: (next: Partial<TranscriptionStatus>) => {
      current = { ...current, ...next }
    },
  }
}

/** A phrase's text, as Nemotron detected its language. */
export function said(text: string, language: string | null = "en"): PhraseText {
  return { text, language, no_speech: false }
}

/** A response the test lets go of when it chooses. */
export function held(response: () => Response) {
  let release = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  return { answer: () => gate.then(response), release: () => release() }
}
