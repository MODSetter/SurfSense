import type { DictationAdapter } from "@assistant-ui/react"

import { QUESTION_MAX_CHARS } from "@/features/chat/question-limit"

import {
  openMicrophone as browserMicrophone,
  type OpenMicrophone,
} from "./capture/open-microphone"
import type { DictationProblem } from "./dictation-problem"
import { Recording, type RecordingView } from "./recording"

/** What the mic and the strip show. */
export type DictationView =
  | { phase: "idle" }
  | RecordingView
  | { phase: "problem"; problem: DictationProblem; canRetry: boolean }

/** The composer methods dictation drives; assistant-ui's composer has them. */
export type DictationComposer = {
  getState: () => { text: string }
  setText: (text: string) => void
  startDictation: () => void
}

export type Dictation = DictationAdapter & {
  subscribe: (listener: () => void) => () => void
  getView: () => DictationView
  /** The microphone's latest RMS level, every 20 ms while listening. */
  subscribeLevel: (listener: () => void) => () => void
  getLevel: () => number
  /** The mic: listens, counting the limit from the text already there. */
  start: (composer: DictationComposer) => void
  /** Click, Enter, Send and a push-to-talk release: the text is kept. */
  stop: () => void
  /** Escape and ✕ pass the composer, which gets its text from before the mic. */
  cancel: (composer?: Pick<DictationComposer, "setText">) => void
  /** Transcribes the audio a failed phrase left, with no microphone. */
  retry: (composer: DictationComposer) => void
  dismiss: () => void
}

const IDLE: DictationView = { phase: "idle" }

/** Room for dictated text: assistant-ui adds a space after text that lacks one. */
function roomAfter(text: string): number {
  const separator = text && !text.endsWith(" ") ? 1 : 0
  return QUESTION_MAX_CHARS - text.length - separator
}

/**
 * Voice input for the chat composer, as assistant-ui's DictationAdapter. One
 * per chat runtime: it outlives a thread switch, which cancels it.
 */
export function createDictation({
  openMicrophone = browserMicrophone,
}: { openMicrophone?: OpenMicrophone } = {}): Dictation {
  let view: DictationView = IDLE
  let level = 0
  const viewListeners = new Set<() => void>()
  const levelListeners = new Set<() => void>()
  let recording: Recording | null = null
  let textBefore = ""
  let kept: Blob[] = []
  let retrying = false

  const show = (next: DictationView) => {
    view = next
    for (const listener of [...viewListeners]) listener()
  }

  const listen = (): DictationAdapter.Session => {
    recording?.cancel()
    const toRetry = retrying ? kept : undefined
    retrying = false
    kept = []
    const current: Recording = new Recording({
      room: roomAfter(textBefore),
      openMicrophone,
      kept: toRetry,
      onView: (next) => {
        if (recording === current) show(next)
      },
      onLevel: (next) => {
        if (recording !== current) return
        level = next
        for (const listener of [...levelListeners]) listener()
      },
      onEnd: ({ problem, kept: left }) => {
        if (recording !== current) return
        recording = null
        level = 0
        kept = problem ? left : []
        show(
          problem
            ? { phase: "problem", problem, canRetry: kept.length > 0 }
            : IDLE
        )
      },
    })
    recording = current
    current.begin()
    return current
  }

  return {
    listen,
    // The textarea goes read-only instead, keeping its focus and its keys.
    disableInputDuringDictation: false,
    subscribe: (listener) => {
      viewListeners.add(listener)
      return () => void viewListeners.delete(listener)
    },
    getView: () => view,
    subscribeLevel: (listener) => {
      levelListeners.add(listener)
      return () => void levelListeners.delete(listener)
    },
    getLevel: () => level,
    start: (composer) => {
      if (recording) return
      textBefore = composer.getState().text
      composer.startDictation()
    },
    stop: () => {
      void recording?.stop()
    },
    cancel: (composer) => {
      kept = []
      const current = recording
      if (current) {
        current.cancel()
        composer?.setText(textBefore)
      } else if (view.phase !== "idle") {
        show(IDLE)
      }
    },
    retry: (composer) => {
      if (recording || kept.length === 0) return
      textBefore = composer.getState().text
      retrying = true
      composer.startDictation()
    },
    dismiss: () => {
      if (recording) return
      kept = []
      show(IDLE)
    },
  }
}
