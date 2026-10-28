import { useId, useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import { pasteCallback } from "./api"

/** Polling the sign-in picks up the result once the API has the code. */
export function PasteCallback({ flowId }: { flowId: string }) {
  const fieldId = useId()
  const [address, setAddress] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await pasteCallback(flowId, address)
    } catch (refused) {
      setBusy(false)
      setError(
        refused instanceof ApiError && refused.code === "not_the_callback"
          ? intl.formatMessage({
              id: "models_chatgpt_paste_wrong_error",
              defaultMessage:
                "That isn’t the address the sign-in sent your browser to. Copy it from the address bar of the tab that showed the error.",
            })
          : intl.formatMessage({
              id: "models_chatgpt_paste_failed_error",
              defaultMessage:
                "SurfSense couldn’t finish the sign-in. Try again.",
            })
      )
    }
  }

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => void submit(event)}
    >
      <Field data-invalid={error ? true : undefined}>
        <FieldLabel htmlFor={fieldId}>
          {intl.formatMessage({
            id: "models_chatgpt_paste_label",
            defaultMessage: "Address your browser ended on",
          })}
        </FieldLabel>
        <FieldDescription>
          {intl.formatMessage({
            id: "models_chatgpt_paste_body",
            defaultMessage:
              "After you agree, your browser shows an error page, since it can’t reach the Docker host’s 127.0.0.1. Copy the address from that tab and paste it here.",
          })}
        </FieldDescription>
        <Input
          id={fieldId}
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="http://127.0.0.1/callback?code=…"
          disabled={busy}
          aria-invalid={error ? true : undefined}
        />
        {error ? <FieldError>{error}</FieldError> : null}
      </Field>
      <Button
        type="submit"
        variant="outline"
        className="w-fit"
        disabled={busy || !address.trim()}
      >
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "models_chatgpt_paste_button",
          defaultMessage: "Finish signing in",
        })}
      </Button>
    </form>
  )
}
