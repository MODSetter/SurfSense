import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext"
import { useAui } from "@assistant-ui/react"
import { mergeRegister } from "@lexical/utils"
import {
  COMMAND_PRIORITY_CRITICAL,
  KEY_ENTER_COMMAND,
  KEY_ESCAPE_COMMAND,
} from "lexical"
import { useEffect } from "react"

import type { Dictation } from "./dictation-adapter"
import { isRecording } from "./use-dictation-view"

// The ways text enters an editor other than keys Lexical sees as commands.
const WRITES = ["beforeinput", "paste", "drop", "cut"]

/**
 * The box while voice input runs. assistant-ui's send() cancels a running session
 * and drops what is not transcribed yet, so Enter stops and inserts instead, and
 * nothing is sent; Escape cancels. The box stays editable, so it keeps its focus
 * and these keys, and refuses writing itself: voice input is writing the text.
 */
export function DictationKeysPlugin({ dictation }: { dictation?: Dictation }) {
  const [editor] = useLexicalComposerContext()
  const aui = useAui()
  useEffect(() => {
    if (!dictation) return undefined
    const holding = () => isRecording(dictation.getView())
    const holdOr = (event: KeyboardEvent | null, act: () => void): boolean => {
      if (!holding() || event?.isComposing) return false
      event?.preventDefault()
      act()
      return true
    }
    const refuse = (event: Event) => {
      if (!holding()) return
      event.preventDefault()
      event.stopImmediatePropagation()
    }
    return mergeRegister(
      editor.registerCommand(
        KEY_ENTER_COMMAND,
        (event) => holdOr(event, () => dictation.stop()),
        COMMAND_PRIORITY_CRITICAL
      ),
      editor.registerCommand(
        KEY_ESCAPE_COMMAND,
        (event) => holdOr(event, () => dictation.cancel(aui.composer())),
        COMMAND_PRIORITY_CRITICAL
      ),
      editor.registerRootListener((root, previous) => {
        for (const kind of WRITES) {
          previous?.removeEventListener(kind, refuse, true)
          root?.addEventListener(kind, refuse, true)
        }
      })
    )
  }, [aui, dictation, editor])
  return null
}
