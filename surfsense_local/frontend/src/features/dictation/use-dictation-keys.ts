import type { MouseEvent } from "react"

import type { Dictation } from "./dictation-adapter"
import { isRecording, useDictationRecording } from "./use-dictation-view"

/** Send while voice input runs stops and inserts instead: assistant-ui's send()
 *  would drop what is not transcribed yet. Its keys: DictationKeysPlugin. */
export function useDictationKeys(dictation?: Dictation) {
  const recording = useDictationRecording(dictation)

  const onSendClick = (event: MouseEvent<HTMLButtonElement>) => {
    if (!dictation || !isRecording(dictation.getView())) return
    event.preventDefault()
    dictation.stop()
  }

  return { recording, onSendClick }
}
