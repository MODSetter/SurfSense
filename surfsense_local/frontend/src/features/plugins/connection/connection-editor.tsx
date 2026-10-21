import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { intl } from "@/i18n/intl"

import type { SignInHeader } from "../api"
import { HeaderRows } from "../headers/header-rows"

/**
 * The headers a server reads its key from, written as the user would anywhere else: the
 * same rows in Add custom plugin and in Edit connection. The user's own OAuth app is never
 * here: it has a dialog of its own.
 */
export function ConnectionEditor({
  rows,
  onChange,
  disabled,
}: {
  rows: SignInHeader[]
  onChange: (rows: SignInHeader[]) => void
  disabled: boolean
}) {
  return (
    <Field>
      <FieldLabel>
        {intl.formatMessage({
          id: "plugins_connection_headers_label",
          defaultMessage: "Headers",
        })}
      </FieldLabel>
      <FieldDescription>
        {intl.formatMessage({
          id: "plugins_connection_headers_body",
          defaultMessage:
            "Most servers read a key as Authorization: Bearer your-key; some name their own header, such as x-api-key.",
        })}
      </FieldDescription>
      <HeaderRows rows={rows} onChange={onChange} disabled={disabled} />
    </Field>
  )
}
