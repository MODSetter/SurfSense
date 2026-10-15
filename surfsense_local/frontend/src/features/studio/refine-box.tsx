import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react"

import { Button } from "@/components/ui/button"
import { AiEditingIcon, ArrowUp02Icon } from "@/components/ui/icons"
import {
  InputGroup,
  InputGroupAddon,
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
  versionShown,
  writingVersion,
  onRefine,
}: {
  artifactId: number
  /** Whether that version's body is on screen; until then nothing is sent. */
  versionShown: boolean
  /** The number of a version of this document being made; the next waits. */
  writingVersion: number | null
  onRefine: (artifactId: number, instruction: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [instruction, setInstruction] = useState("")
  const [isSending, setIsSending] = useState(false)
  // Kept with the version it refused, so another version opening clears it.
  const [refused, setRefused] = useState<{
    artifactId: number
    reason: string
  } | null>(null)
  const refusal = refused?.artifactId === artifactId ? refused.reason : null
  const errorId = useId()
  const field = useRef<HTMLTextAreaElement>(null)
  const openButton = useRef<HTMLButtonElement>(null)
  const box = useRef<HTMLFormElement>(null)
  const pill = useRef<HTMLSpanElement>(null)
  // Where focus goes once a fold either way has made its target focusable.
  const refocusButton = useRef(false)
  const empty = instruction.trim() === ""
  const state = open ? "open" : writingVersion !== null ? "making" : "folded"
  // Held after the version is ready, so the pill's text fades rather than blanks.
  const [shownVersion, setShownVersion] = useState(writingVersion)
  if (writingVersion !== null && writingVersion !== shownVersion) {
    setShownVersion(writingVersion)
  }
  const blocked = empty || !versionShown || writingVersion !== null || isSending

  const close = (returnFocus: boolean) => {
    setOpen(false)
    setRefused(null)
    refocusButton.current = returnFocus
  }

  const send = async () => {
    if (blocked) return
    setIsSending(true)
    setRefused(null)
    try {
      await onRefine(artifactId, instruction.trim())
      setInstruction("")
      close(false)
    } catch (cause) {
      setRefused({ artifactId, reason: messageFrom(cause) })
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

  // The pill's width as a length, so the box reaches it and leaves it by a
  // plain transition. An `auto` width would be re-measured every frame, and
  // with the pill out of flow it measures nothing: the box collapses first.
  useLayoutEffect(() => {
    const width = pill.current?.offsetWidth
    // Plus the box's 1px border either side.
    if (width) box.current?.style.setProperty("--pill-width", `${width + 2}px`)
  }, [shownVersion])

  const openLabel = intl.formatMessage({
    id: "studio_refine_open_aria",
    defaultMessage: "Refine this document",
  })

  const makingLabel = (version: number) =>
    intl.formatMessage(
      {
        id: "studio_refine_writing_status",
        defaultMessage: "Making version {version, number}…",
      },
      { version }
    )

  // One box that stays mounted through its three faces (the button, the
  // instruction, the version being made), so every change between them is
  // the same interruptible CSS transition of width and height, with no
  // element swapped in or out. `interpolate-size` lets the height reach the
  // draft's `auto`, which stays in flow so that measure holds while folding.
  return (
    <form
      ref={box}
      data-state={state}
      onSubmit={onSubmit}
      onBlur={onBlur}
      // A pill on one line (50px tall), like the folded button and the status pill;
      // a fixed radius rather than rounded-full keeps a long draft a box.
      // Eased in and out, with no long settle that reads as a spring. It also
      // fades in when it mounts, as it does each time a version opens.
      className="pointer-events-auto relative flex h-[50px] w-[50px] animate-in items-end justify-end overflow-hidden rounded-[25px] border bg-card shadow-lg transition-[width,height,border-color] duration-250 ease-in-out fade-in-0 [interpolate-size:allow-keywords] not-data-[state=making]:focus-within:border-ring/40 not-data-[state=making]:hover:border-ring/40 data-[state=making]:w-(--pill-width) data-[state=open]:h-auto data-[state=open]:w-full motion-reduce:animate-none motion-reduce:transition-none"
    >
      {/* Laid out at the open width at all times (the wrapper's, in cqw), so
          a narrow box clips it rather than reflowing the text and changing
          the height mid-way. Held to the bottom right by items-end and
          justify-end, so a folding draft shrinks onto the button. */}
      <div
        inert={!open}
        // inert hides it from the browser's accessibility tree; aria-hidden
        // says the same to anything that reads ARIA alone.
        aria-hidden={!open}
        className="w-[100cqw] shrink-0 p-1.5 opacity-0 transition-opacity duration-150 motion-reduce:transition-none [[data-state=open]>&]:opacity-100 [[data-state=open]>&]:delay-75"
      >
        {/* The group greys itself out when any child is disabled; here that is
            only the send button while empty, which must not dim the field. */}
        <InputGroup className="h-auto border-0 has-disabled:bg-transparent has-disabled:opacity-100 dark:bg-transparent dark:has-disabled:bg-transparent">
          <InputGroupTextarea
            ref={field}
            rows={1}
            className="max-h-40 min-h-9 py-2 text-sm"
            value={instruction}
            maxLength={INSTRUCTION_CHARS}
            onChange={(event) => {
              setInstruction(event.target.value)
              setRefused(null)
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
          {/* Held at the last line as the instruction grows, as in the chat
              composer; the addon's own stretch would centre it instead. */}
          <InputGroupAddon
            align="inline-end"
            className="has-[>button]:self-end"
          >
            {/* Round, inset 7px from the 25px corner, so the two curves share a centre. */}
            <Button
              type="submit"
              size="icon-lg"
              className="rounded-full"
              disabled={blocked}
              aria-label={intl.formatMessage({
                id: "studio_refine_submit_button",
                defaultMessage: "Refine",
              })}
            >
              {isSending ? <Spinner /> : <ArrowUp02Icon />}
            </Button>
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
      {/* The version being made, measured for the box's width while making;
          the live region apart from it says it once, and is empty otherwise. */}
      <span
        ref={pill}
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 flex items-center gap-2 px-4 text-sm whitespace-nowrap text-muted-foreground opacity-0 transition-opacity duration-150 select-none motion-reduce:transition-none [[data-state=making]>&]:opacity-100 [[data-state=making]>&]:delay-75"
      >
        <Spinner />
        {shownVersion !== null ? makingLabel(shownVersion) : null}
      </span>
      <span role="status" className="sr-only">
        {state === "making" && writingVersion !== null
          ? makingLabel(writingVersion)
          : null}
      </span>
      {/* The folded face, over the box's right end; fades as it opens. */}
      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              ref={openButton}
              type="button"
              variant="ghost"
              size="icon-lg"
              inert={state !== "folded"}
              aria-hidden={state !== "folded"}
              className="pointer-events-none absolute -right-px -bottom-px size-[50px] rounded-full opacity-0 transition-opacity duration-150 motion-reduce:transition-none [[data-state=folded]>&]:pointer-events-auto [[data-state=folded]>&]:opacity-100"
              aria-label={openLabel}
              onClick={() => setOpen(true)}
            >
              <AiEditingIcon className="size-5" />
              {/* A draft is waiting from the last time it was open. */}
              {!empty ? (
                <span className="absolute top-2.5 right-2.5 size-1.5 rounded-full bg-primary" />
              ) : null}
            </Button>
          }
        />
        <TooltipContent side="top">{openLabel}</TooltipContent>
      </Tooltip>
    </form>
  )
}
