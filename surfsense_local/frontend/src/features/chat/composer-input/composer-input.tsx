import { EditorRefPlugin } from "@lexical/react/LexicalEditorRefPlugin"
import { LexicalComposerInput } from "@assistant-ui/react-lexical"
import { $getSelection, $isRangeSelection, type LexicalEditor } from "lexical"
import { useRef, type ReactNode } from "react"

import { cn } from "@/lib/utils"

import { composerTextClassName } from "../composer-text-class"
import { ComposerMentionChip } from "../mentions/composer-mention-chip"
import { QUESTION_MAX_CHARS } from "../question-limit"
import { HeldWhileBlockedPlugin } from "./held-while-blocked-plugin"
import { ImagePastePlugin } from "./image-paste-plugin"
import { TextLimitPlugin } from "./text-limit-plugin"

/** The message box: rich, so a named source sits in the text as a chip. */
export function ComposerInput({
  placement,
  blocked,
  autoFocus,
  describedBy,
  placeholder,
  ariaLabel,
  takesImages,
  children,
}: {
  placement: "center" | "bottom"
  // Held whenever a send could not go anywhere.
  blocked: boolean
  autoFocus: boolean
  describedBy?: string
  placeholder: string
  ariaLabel: string
  takesImages: boolean
  // Plugins of the features that write into the box.
  children?: ReactNode
}) {
  const editor = useRef<LexicalEditor | null>(null)
  return (
    <LexicalComposerInput
      data-reveal-steady=""
      className={cn(composerTextClassName(placement), "composer-input")}
      autoFocus={autoFocus}
      aria-describedby={describedBy}
      aria-label={ariaLabel}
      placeholder={placeholder}
      submitMode="enter"
      directiveChip={ComposerMentionChip}
      directivePluginProps={{
        // As a typed word would: the next word starts clear of the chip.
        onDirectiveSelect: () =>
          editor.current?.update(() => {
            const selection = $getSelection()
            if ($isRangeSelection(selection)) selection.insertRawText(" ")
          }),
      }}
    >
      <EditorRefPlugin editorRef={editor} />
      <HeldWhileBlockedPlugin blocked={blocked} />
      <TextLimitPlugin max={QUESTION_MAX_CHARS} />
      <ImagePastePlugin enabled={takesImages} />
      {children}
    </LexicalComposerInput>
  )
}
