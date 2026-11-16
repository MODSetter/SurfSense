import { ApiError } from "@/lib/api"

/** Why a recording ended other than by the user, or could not start. */
export type DictationProblem =
  | {
      kind:
        | "microphone_off"
        | "no_microphone"
        | "microphone_busy"
        | "microphone_failed"
        | "needs_secure_connection"
        | "microphone_disconnected"
        | "phrase_failed"
        | "at_limit"
        | "time_limit"
        | "dictation_ended"
        | "model_removed"
        | "needs_speech_model"
        | "transcription_unavailable"
    }
  | {
      kind: "transcription_needs_memory"
      neededBytes: number
      availableBytes: number
      /** The API's English sentence, for when the sizes are missing. */
      message: string
    }

/** getUserMedia's own error names, and the system switch read as NotAllowedError. */
export function microphoneProblem(error: unknown): DictationProblem {
  // Outside HTTPS and the host itself, as the Docker image is from another
  // device over HTTP, the browser offers no microphone at all.
  if (window.isSecureContext === false)
    return { kind: "needs_secure_connection" }
  const name = error instanceof DOMException ? error.name : ""
  if (name === "NotAllowedError" || name === "SecurityError") {
    return { kind: "microphone_off" }
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return { kind: "no_microphone" }
  }
  if (name === "NotReadableError" || name === "AbortError") {
    return { kind: "microphone_busy" }
  }
  return { kind: "microphone_failed" }
}

/** The API's memory refusal, at the session's start or on a phrase. */
export function memoryProblem(error: unknown): DictationProblem | null {
  if (!(error instanceof ApiError)) return null
  if (error.code !== "transcription_needs_memory") return null
  return {
    kind: "transcription_needs_memory",
    neededBytes: Number(error.detail.needed_bytes),
    availableBytes: Number(error.detail.available_bytes),
    message: error.message,
  }
}

/** A refusal to open a session, by its code; anything else is a server not answering. */
export function openingProblem(error: unknown): DictationProblem {
  if (!(error instanceof ApiError)) return { kind: "transcription_unavailable" }
  if (error.code === "needs_speech_model") return { kind: "needs_speech_model" }
  return memoryProblem(error) ?? { kind: "transcription_unavailable" }
}
