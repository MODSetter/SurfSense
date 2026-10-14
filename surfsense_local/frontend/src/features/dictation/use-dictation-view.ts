import { useSyncExternalStore } from "react"

import type { Dictation, DictationView } from "./dictation-adapter"

const IDLE: DictationView = { phase: "idle" }
const nothingToHear = () => () => {}
const idle = () => IDLE

/** A recording holds the composer, from the mic press to its final text. */
export function isRecording(view: DictationView): boolean {
  return (
    view.phase === "arming" ||
    view.phase === "listening" ||
    view.phase === "finishing"
  )
}

/** What the mic and the strip show; idle where the composer has no dictation. */
export function useDictationView(dictation?: Dictation): DictationView {
  return useSyncExternalStore(
    dictation?.subscribe ?? nothingToHear,
    dictation?.getView ?? idle
  )
}

/** Changes only when a recording starts or ends, not with every phrase. */
export function useDictationRecording(dictation?: Dictation): boolean {
  return useSyncExternalStore(dictation?.subscribe ?? nothingToHear, () =>
    dictation ? isRecording(dictation.getView()) : false
  )
}

/** Whether the strip shows at all: recording, or a problem to read. */
export function useDictationStripShown(dictation?: Dictation): boolean {
  return useSyncExternalStore(dictation?.subscribe ?? nothingToHear, () =>
    dictation ? dictation.getView().phase !== "idle" : false
  )
}
