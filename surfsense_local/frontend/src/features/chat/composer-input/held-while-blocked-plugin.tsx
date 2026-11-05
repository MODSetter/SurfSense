import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext"
import { useAuiState } from "@assistant-ui/react"
import { useEffect } from "react"

/** The box takes nothing while a send could not go anywhere, nor while the thread
 *  or the composer holds it; the package's own check knows only the last two. */
export function HeldWhileBlockedPlugin({ blocked }: { blocked: boolean }) {
  const [editor] = useLexicalComposerContext()
  const held = useAuiState(
    (s) =>
      s.thread.isDisabled || (s.composer.dictation?.inputDisabled ?? false)
  )
  useEffect(() => {
    editor.setEditable(!(blocked || held))
  }, [blocked, editor, held])
  return null
}
