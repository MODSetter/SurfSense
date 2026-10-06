import { useId, useState, type FormEvent, type KeyboardEvent } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { intl } from "@/i18n/intl"

import { messageFrom } from "./use-studio"

// The longest instruction POST /artifacts/{id}/refine accepts.
const INSTRUCTION_CHARS = 2000

/** Asks for the next version of the open document, rewritten to an
 *  instruction in one model call. */
export function RefineBox({
  artifactId,
  versionRunning,
  onRefine,
}: {
  artifactId: number
  /** A version of this document is being made; the next waits for it. */
  versionRunning: boolean
  onRefine: (artifactId: number, instruction: string) => Promise<void>
}) {
  const [instruction, setInstruction] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [refusal, setRefusal] = useState<string | null>(null)
  const errorId = useId()
  const blocked = instruction.trim() === "" || versionRunning || isSending

  const send = async () => {
    if (blocked) return
    setIsSending(true)
    setRefusal(null)
    try {
      await onRefine(artifactId, instruction.trim())
      setInstruction("")
    } catch (cause) {
      setRefusal(messageFrom(cause))
    } finally {
      setIsSending(false)
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void send()
  }

  // Enter alone writes a new line; Ctrl or Cmd with it sends.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="flex shrink-0 flex-col gap-2 border-t px-3 py-3"
    >
      <Textarea
        className="max-h-40 min-h-14 resize-none"
        value={instruction}
        maxLength={INSTRUCTION_CHARS}
        onChange={(event) => {
          setInstruction(event.target.value)
          setRefusal(null)
        }}
        onKeyDown={onKeyDown}
        aria-label={intl.formatMessage({
          id: "studio_refine_instruction_aria",
          defaultMessage: "How to change this document",
        })}
        aria-invalid={refusal ? true : undefined}
        aria-describedby={refusal ? errorId : undefined}
        placeholder={intl.formatMessage({
          id: "studio_refine_instruction_placeholder",
          defaultMessage: "Describe a change, such as a shorter introduction",
        })}
      />
      <div className="flex items-start justify-between gap-3">
        <p id={errorId} role="alert" className="text-sm text-destructive">
          {refusal}
        </p>
        <Button type="submit" size="sm" disabled={blocked}>
          {isSending ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "studio_refine_submit_button",
            defaultMessage: "Refine",
          })}
        </Button>
      </div>
    </form>
  )
}
