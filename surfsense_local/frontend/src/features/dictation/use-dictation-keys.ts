import type { KeyboardEvent, MouseEvent } from "react"
import { useAui } from "@assistant-ui/react"

import type { Dictation } from "./dictation-adapter"
import { isRecording, useDictationRecording } from "./use-dictation-view"

/**
 * The composer's keys while voice input runs. assistant-ui's send() cancels a
 * running session and drops what is not transcribed yet, so Enter and Send
 * stop and insert instead, and nothing is sent; Escape cancels.
 */
export function useDictationKeys(dictation?: Dictation) {
  const aui = useAui()
  const recording = useDictationRecording(dictation)

  const holding = () =>
    dictation !== undefined && isRecording(dictation.getView())

  // Runs before assistant-ui's own handler, which a preventDefault skips.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!holding() || event.nativeEvent.isComposing) return
    if (event.key === "Enter") {
      event.preventDefault()
      dictation?.stop()
    } else if (event.key === "Escape") {
      event.preventDefault()
      dictation?.cancel(aui.composer())
    }
  }

  const onSendClick = (event: MouseEvent<HTMLButtonElement>) => {
    if (!holding()) return
    event.preventDefault()
    dictation?.stop()
  }

  return { recording, onKeyDown, onSendClick }
}
