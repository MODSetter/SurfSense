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

/** From the first real frame to the final text: the strip and Stop and insert show. */
export function hasStarted(view: DictationView): boolean {
  return view.phase === "listening" || view.phase === "finishing"
}

/** Changes only when that starts or ends, not with every phrase. */
export function useDictationStarted(dictation?: Dictation): boolean {
  return useSyncExternalStore(dictation?.subscribe ?? nothingToHear, () =>
    dictation ? hasStarted(dictation.getView()) : false
  )
}

/** Changes only when a recording starts or ends, not with every phrase. */
export function useDictationRecording(dictation?: Dictation): boolean {
  return useSyncExternalStore(dictation?.subscribe ?? nothingToHear, () =>
    dictation ? isRecording(dictation.getView()) : false
  )
}
