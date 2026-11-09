import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { CheckIcon, CopyIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { useCopyToClipboard } from "@/features/about/use-copy-to-clipboard"
import { intl } from "@/i18n/intl"

/** A build signing in on this computer's own port, whose address moves with it. */
function movesOnRestart(address: string): boolean {
  return /^http:\/\/(127\.0\.0\.1|localhost)[:/]/.test(address)
}

/** The address to register the user's app with, copied in one click: the step people get wrong. */
export function CallbackAddress({
  id,
  address,
}: {
  id: string
  /** Null while the API has not said which callback this build signs in with. */
  address: string | null
}) {
  // The tick shows for a moment, then the copy icon is back, as on every copy button.
  const { copied, copy } = useCopyToClipboard(address ?? "")
  return (
    <Field>
      {/* The step's own title says what it is; the label names the field for assistive tech. */}
      <FieldLabel htmlFor={id} className="sr-only">
        {intl.formatMessage({
          id: "plugins_own_app_callback_label",
          defaultMessage: "Callback address",
        })}
      </FieldLabel>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          readOnly
          value={address ?? ""}
          className="flex-1 font-mono text-xs select-text"
        />
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          disabled={!address}
          data-copied={copied}
          aria-label={intl.formatMessage({
            id: "plugins_own_app_callback_copy_aria",
            defaultMessage: "Copy the callback address",
          })}
          onClick={() => void copy()}
        >
          {copied ? <CheckIcon /> : <CopyIcon />}
        </Button>
      </div>
      {address && movesOnRestart(address) ? (
        <FieldDescription>
          {intl.formatMessage({
            id: "plugins_own_app_callback_moves_body",
            defaultMessage:
              "This developer build’s address changes each time the app restarts; register it again after one.",
          })}
        </FieldDescription>
      ) : null}
    </Field>
  )
}
