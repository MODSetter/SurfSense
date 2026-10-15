import { intl } from "@/i18n/intl"
import { QUESTION_MAX_CHARS } from "@/features/chat/question-limit"

import type { DictationProblem } from "../dictation-problem"

/** The one thing the problem line offers. */
export type ProblemAction =
  "open_settings" | "retry" | "try_again" | "set_up" | "dismiss"

/** A stop the user can expect, said politely rather than as an alert. */
export function isNotice(problem: DictationProblem): boolean {
  return problem.kind === "at_limit" || problem.kind === "time_limit"
}

/** Only Windows and macOS have a microphone switch the app can open. */
function systemHasMicrophoneSettings(): boolean {
  const bridge = window.surfsense
  return (
    bridge?.microphone !== undefined &&
    (bridge.platform === "win32" || bridge.platform === "darwin")
  )
}

export function problemAction(
  problem: DictationProblem,
  { canRetry, canSetUp }: { canRetry: boolean; canSetUp: boolean }
): ProblemAction {
  switch (problem.kind) {
    case "microphone_off":
      return systemHasMicrophoneSettings() ? "open_settings" : "try_again"
    case "no_microphone":
    case "microphone_busy":
    case "microphone_failed":
    case "transcription_unavailable":
      return "try_again"
    case "phrase_failed":
    case "transcription_needs_memory":
      return canRetry ? "retry" : "dismiss"
    case "needs_speech_model":
    case "model_removed":
      return canSetUp ? "set_up" : "dismiss"
    default:
      return "dismiss"
  }
}

const GIGABYTE = 1e9

export function problemText(problem: DictationProblem): string {
  switch (problem.kind) {
    case "microphone_off":
      return intl.formatMessage({
        id: "dictation_strip_microphone_off_error",
        defaultMessage: "Microphone access is off for SurfSense.",
      })
    case "no_microphone":
      return intl.formatMessage({
        id: "dictation_strip_no_microphone_error",
        defaultMessage: "No microphone found.",
      })
    case "microphone_busy":
      return intl.formatMessage({
        id: "dictation_strip_microphone_busy_error",
        defaultMessage: "The microphone is in use by another app.",
      })
    case "microphone_failed":
      return intl.formatMessage({
        id: "dictation_strip_microphone_failed_error",
        defaultMessage: "The microphone couldn’t start.",
      })
    case "microphone_disconnected":
      return intl.formatMessage({
        id: "dictation_strip_microphone_disconnected_error",
        defaultMessage:
          "The microphone was disconnected. What you said before that is kept.",
      })
    case "phrase_failed":
      return intl.formatMessage({
        id: "dictation_strip_phrase_failed_error",
        defaultMessage: "Couldn’t turn part of your speech into text.",
      })
    case "at_limit":
      return intl.formatMessage(
        {
          id: "dictation_strip_at_limit_status",
          defaultMessage:
            "Voice input stopped at the {max, number}-character message limit.",
        },
        { max: QUESTION_MAX_CHARS }
      )
    case "time_limit":
      return intl.formatMessage(
        {
          id: "dictation_strip_time_limit_status",
          defaultMessage:
            "Voice input stopped after {minutes, plural, one {# minute} other {# minutes}}.",
        },
        { minutes: 5 }
      )
    case "model_removed":
      return intl.formatMessage({
        id: "dictation_strip_model_removed_error",
        defaultMessage: "The speech recognition model was removed.",
      })
    case "dictation_ended":
      return intl.formatMessage({
        id: "dictation_error_dictation_ended",
        defaultMessage: "Voice input stopped; what was transcribed is kept.",
      })
    case "needs_speech_model":
      return intl.formatMessage({
        id: "dictation_error_needs_speech_model",
        defaultMessage: "Set up speech recognition to use voice input.",
      })
    case "transcription_unavailable":
      return intl.formatMessage({
        id: "dictation_error_transcription_unavailable",
        defaultMessage: "Speech recognition isn’t available right now.",
      })
    case "transcription_needs_memory":
      // The server's sentence when it sent no sizes to format.
      return Number.isFinite(problem.neededBytes) &&
        Number.isFinite(problem.availableBytes)
        ? intl.formatMessage(
            {
              id: "dictation_error_transcription_needs_memory",
              defaultMessage:
                "Transcribing needs about {needed, number, ::unit/gigabyte .#} free; this computer has {available, number, ::unit/gigabyte .#}.",
            },
            {
              needed: problem.neededBytes / GIGABYTE,
              available: problem.availableBytes / GIGABYTE,
            }
          )
        : problem.message
  }
}
