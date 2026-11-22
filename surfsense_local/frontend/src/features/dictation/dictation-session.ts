import { ApiError } from "@/lib/api"

import {
  endDictation,
  keepDictationAlive,
  openDictation,
  transcribePhrase,
  type PhraseText,
} from "./api"

// The API ends a session after 20 s without a phrase or a keepalive.
const KEEPALIVE_MS = 10_000
const RETRY_AFTER_MS = 2_000

export type DictationSession = {
  warm: "loaded" | "loading"
  /** Queued behind the phrases before it: one is in flight at a time. */
  transcribe: (wav: Blob) => Promise<PhraseText>
  /** Stops the keepalive and releases the API's session; safe to repeat. */
  end: () => void
}

/** The API no longer knows the session, as after it restarted. */
export function isDictationEnded(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    error.code === "dictation_ended"
  )
}

// A refused connection or a server mid-restart; not a refusal of the phrase.
function worthAnotherTry(error: unknown): boolean {
  return (
    error instanceof TypeError ||
    (error instanceof ApiError && error.status === 503)
  )
}

const pause = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms))

/** One recording's session with the API, from the mic press to its last phrase. */
export async function openDictationSession({
  onEnded,
}: {
  /** The API dropped the session, which a keepalive found out. */
  onEnded: () => void
}): Promise<DictationSession> {
  const { id, warm } = await openDictation()
  let ended = false
  let queue: Promise<unknown> = Promise.resolve()

  const end = () => {
    if (ended) return
    ended = true
    clearInterval(keepalive)
    void endDictation(id).catch(() => undefined)
  }

  const keepalive = setInterval(() => {
    keepDictationAlive(id).catch((error: unknown) => {
      if (!isDictationEnded(error) || ended) return
      end()
      onEnded()
    })
  }, KEEPALIVE_MS)

  const send = async (wav: Blob) => {
    try {
      return await transcribePhrase(id, wav)
    } catch (error) {
      if (!worthAnotherTry(error)) throw error
      await pause(RETRY_AFTER_MS)
      return transcribePhrase(id, wav)
    }
  }

  return {
    warm,
    transcribe: (wav) => {
      const result = queue.then(() => send(wav))
      queue = result.catch(() => undefined)
      return result
    },
    end,
  }
}
