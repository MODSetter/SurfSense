import type { Ref } from "react"

import { Button } from "@/components/ui/button"
import { CircleAlertIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { EDIT_MODEL_CODE, type RefineSubject } from "./edit-model"
import { studioCodeText } from "./studio-error-text"

/** Why the edit box cannot be used yet, in the chat composer's notice style:
 *  a tab the box paints over, with the way to choose the missing model. */
export function EditModelNotice({
  subject,
  chooseButton,
  onChooseModel,
  onEscape,
}: {
  subject: RefineSubject
  chooseButton: Ref<HTMLButtonElement>
  onChooseModel?: () => void
  onEscape: () => void
}) {
  return (
    <div
      role="status"
      // Rounded as the box is, 25px, and as deep below the text as the box
      // tucks it, so its sides run on into the box's below the curve. Faded in
      // once the box has opened (250ms), held hidden until then.
      className="flex animate-in items-center gap-2 rounded-t-[25px] border border-b-0 bg-muted px-4 pt-1.5 pb-[29px] text-xs text-muted-foreground delay-250 fade-in-0 fill-mode-backwards motion-reduce:animate-none"
    >
      <CircleAlertIcon className="size-4 shrink-0 text-destructive" />
      <p className="min-w-0 flex-1 text-pretty">
        {studioCodeText(EDIT_MODEL_CODE[subject])}
      </p>
      {onChooseModel ? (
        <Button
          ref={chooseButton}
          type="button"
          variant="outline"
          size="xs"
          className="h-5 shrink-0"
          onClick={onChooseModel}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return
            event.stopPropagation()
            onEscape()
          }}
        >
          {intl.formatMessage({
            id: "studio_refine_choose_model_button",
            defaultMessage: "Choose a model",
          })}
        </Button>
      ) : null}
    </div>
  )
}
