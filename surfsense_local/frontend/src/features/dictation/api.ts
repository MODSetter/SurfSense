import { requestJson, requestVoid } from "@/lib/api"

const ROOT = "/llm/transcription"

/** Whether voice input can start, and why not; the mic reads it. */
export type TranscriptionStatus = {
  ready: boolean
  reason: "needs_speech_model" | "transcription_unavailable" | null
  model: string | null
  language_intent: string
  languages: string[]
}

export type OpenedDictation = {
  id: string
  /** `loading` while the model loads for this session's first phrase. */
  warm: "loaded" | "loading"
}

export type PhraseText = {
  text: string
  /** ISO 639-1, detected or pinned; null when neither says. */
  language: string | null
  no_speech: boolean
}

export function readTranscriptionStatus(
  signal?: AbortSignal
): Promise<TranscriptionStatus> {
  return requestJson<TranscriptionStatus>(`${ROOT}/status`, { signal })
}

export function openDictation(): Promise<OpenedDictation> {
  return requestJson<OpenedDictation>(`${ROOT}/dictations`, { method: "POST" })
}

/** One phrase: a WAV of 16 kHz mono 16-bit PCM, at most 30 s. */
export function transcribePhrase(id: string, wav: Blob): Promise<PhraseText> {
  const body = new FormData()
  body.append("audio", wav, "phrase.wav")
  return requestJson<PhraseText>(
    `${ROOT}/dictations/${encodeURIComponent(id)}/phrases`,
    { method: "POST", body }
  )
}

export function keepDictationAlive(id: string): Promise<void> {
  return requestVoid(`${ROOT}/dictations/${encodeURIComponent(id)}/keepalive`, {
    method: "POST",
  })
}

export function endDictation(id: string): Promise<void> {
  // Outlives the page, so a closing window still releases the gate.
  return requestVoid(`${ROOT}/dictations/${encodeURIComponent(id)}`, {
    method: "DELETE",
    keepalive: true,
  })
}
