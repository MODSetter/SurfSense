import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react"

import { Button } from "@/components/ui/button"
import { ArrowUp02Icon, PencilEdit02Icon } from "@/components/ui/icons"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"

import { messageFrom } from "./use-studio"

// The longest instruction POST /artifacts/{id}/refine accepts.
const INSTRUCTION_CHARS = 2000

/** Asks for the next version of the open document, rewritten to an
 *  instruction in one model call. A round button until opened, so the
 *  document keeps the panel; the version being made shows in its place. */
export function RefineBox({
  artifactId,
  writingVersion,
  onRefine,
}: {
  artifactId: number
  /** The number of a version of this document being made; the next waits. */
  writingVersion: number | null
  onRefine: (artifactId: number, instruction: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [instruction, setInstruction] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [refusal, setRefusal] = useState<string | null>(null)
  const errorId = useId()
  const field = useRef<HTMLTextAreaElement>(null)
  const openButton = useRef<HTMLButtonElement>(null)
  // Where focus goes once a fold either way has made its target focusable.
  const refocusButton = useRef(false)
  const empty = instruction.trim() === ""
  const blocked = empty || writingVersion !== null || isSending

  const close = (returnFocus: boolean) => {
    setOpen(false)
    setRefusal(null)
    refocusButton.current = returnFocus
  }

  const send = async () => {
    if (blocked) return
    setIsSending(true)
    setRefusal(null)
    try {
      await onRefine(artifactId, instruction.trim())
      setInstruction("")
      close(false)
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

  // Enter sends and Shift+Enter writes a new line, as in the chat composer.
  // Enter that confirms an IME composition sends nothing.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Escape") {
      // Keeps the panel around it from closing too.
      event.stopPropagation()
      close(true)
      return
    }
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault()
      void send()
    }
  }

  // A click anywhere else folds it away; what was typed stays for next time.
  const onBlur = (event: FocusEvent<HTMLFormElement>) => {
    if (isSending || refusal) return
    if (!event.currentTarget.contains(event.relatedTarget)) close(false)
  }

  // Focus moves once the render has lifted `inert` from its target.
  useEffect(() => {
    if (open) {
      field.current?.focus()
    } else if (refocusButton.current) {
      refocusButton.current = false
      openButton.current?.focus()
    }
  }, [open])

  if (writingVersion !== null && !open) {
    return (
      <p
        role="status"
        className="pointer-events-auto flex h-11 items-center gap-2 rounded-full bg-popover px-4 text-sm text-muted-foreground shadow-lg"
      >
        {/* The pill is the announcement; a second "Loading" adds nothing. */}
        <Spinner aria-hidden />
        {intl.formatMessage(
          {
            id: "studio_refine_writing_status",
            defaultMessage: "Writing v{version, number}…",
          },
          { version: writingVersion }
        )}
      </p>
    )
  }

  const openLabel = intl.formatMessage({
    id: "studio_refine_open_aria",
    defaultMessage: "Refine this document",
  })

  // One box that stays mounted and changes width, so opening and closing are
  // the same CSS transition run either way, interruptible midway, with no
  // element swapped in or out. Both widths are lengths (2.75rem and 100%),
  // which is what lets `width` transition. Sizing the box to its content
  // instead (`w-auto`) would need `interpolate-size: allow-keywords` on it,
  // or `calc-size()`, to keep animating: CSS that animates to `auto`.
  return (
    <form
      data-open={open}
      onSubmit={onSubmit}
      onBlur={onBlur}
      // Opaque and raised: it floats over the document's white pages.
      // iOS's sheet curve: fast out, settling in, as a spring would.
      className="pointer-events-auto relative flex w-11 justify-end overflow-hidden rounded-[22px] bg-popover shadow-lg transition-[width,border-radius] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] data-[open=true]:w-full data-[open=true]:rounded-xl motion-reduce:transition-none"
    >
      {/* Laid out at the open width at all times (the wrapper's, in cqw),
          and held to the right by justify-end, which lets it overflow
          leftward: a narrow box clips it rather than reflowing the text and
          changing the height mid-way. Inert while folded. */}
      <div
        inert={!open}
        // inert hides it from the browser's accessibility tree; aria-hidden
        // says the same to anything that reads ARIA alone.
        aria-hidden={!open}
        className="w-[100cqw] shrink-0 p-1 opacity-0 transition-opacity duration-150 motion-reduce:transition-none [[data-open=true]>&]:opacity-100 [[data-open=true]>&]:delay-75"
      >
        <InputGroup className="h-auto border-0 dark:bg-transparent">
          <InputGroupTextarea
            ref={field}
            rows={1}
            className="max-h-40 min-h-0 text-sm"
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
              defaultMessage:
                "Describe a change, such as a shorter introduction",
            })}
          />
          {/* Held at the last line as the instruction grows. */}
          <InputGroupAddon align="inline-end" className="self-end">
            <InputGroupButton
              type="submit"
              size="icon-xs"
              variant={empty ? "secondary" : "default"}
              className="rounded-full"
              disabled={blocked}
              aria-label={intl.formatMessage({
                id: "studio_refine_submit_button",
                defaultMessage: "Refine",
              })}
            >
              {isSending ? <Spinner /> : <ArrowUp02Icon />}
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
        {/* Mounted while empty, so a screen reader hears the refusal arrive.
            Its row opens from 0fr, so the box grows to it instead of jumping. */}
        <div className="grid grid-rows-[0fr] transition-[grid-template-rows] duration-200 has-[p:not(:empty)]:grid-rows-[1fr] motion-reduce:transition-none">
          <p
            id={errorId}
            role="alert"
            className="min-h-0 overflow-hidden px-2.5 text-sm text-destructive [&:not(:empty)]:pb-1.5"
          >
            {refusal}
          </p>
        </div>
      </div>
      {/* The folded face, over the box's right end; fades as it opens. */}
      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              ref={openButton}
              type="button"
              variant="ghost"
              size="icon-lg"
              inert={open}
              aria-hidden={open}
              className="absolute right-0 bottom-0 size-11 rounded-full transition-opacity duration-150 motion-reduce:transition-none [[data-open=true]>&]:pointer-events-none [[data-open=true]>&]:opacity-0"
              aria-label={openLabel}
              onClick={() => setOpen(true)}
            >
              <PencilEdit02Icon />
              {/* A draft is waiting from the last time it was open. */}
              {!empty ? (
                <span className="absolute top-2 right-2 size-1.5 rounded-full bg-primary" />
              ) : null}
            </Button>
          }
        />
        <TooltipContent side="top">{openLabel}</TooltipContent>
      </Tooltip>
    </form>
  )
}
