import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext"
import { useAui } from "@assistant-ui/react"
import { COMMAND_PRIORITY_HIGH, PASTE_COMMAND } from "lexical"
import { useEffect } from "react"

import { errorToast } from "@/features/feedback/error-toast"

/** A pasted file becomes an attachment, while this chat takes them. */
export function ImagePastePlugin({ enabled }: { enabled: boolean }) {
  const [editor] = useLexicalComposerContext()
  const aui = useAui()
  useEffect(
    () =>
      editor.registerCommand(
        PASTE_COMMAND,
        (event) => {
          if (!enabled || !("clipboardData" in event)) return false
          const files = [...(event.clipboardData?.files ?? [])]
          if (
            files.length === 0 ||
            !aui.thread.getState().capabilities.attachments
          ) {
            return false
          }
          event.preventDefault()
          for (const file of files) {
            void aui
              .composer()
              .addAttachment(file)
              .catch((cause: unknown) =>
                errorToast(cause instanceof Error ? cause.message : String(cause))
              )
          }
          return true
        },
        COMMAND_PRIORITY_HIGH
      ),
    [aui, editor, enabled]
  )
  return null
}
