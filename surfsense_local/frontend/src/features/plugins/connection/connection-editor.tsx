import { useId } from "react"

import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { PlusIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"

import { HeaderRows } from "../headers/header-rows"
import type { ConnectionDraft } from "./connection-draft"
import { SendAsControl } from "./send-as-control"

/**
 * A key and how it is sent, and further headers: the same fields in Add custom plugin and
 * in Edit connection. The user's own OAuth app is never here: it has a dialog of its own.
 */
export function ConnectionEditor({
  draft,
  onChange,
  disabled,
}: {
  draft: ConnectionDraft
  onChange: (draft: ConnectionDraft) => void
  disabled: boolean
}) {
  const fieldId = useId()
  const change = (part: Partial<ConnectionDraft>) =>
    onChange({ ...draft, ...part })
  return (
    <>
      <Field>
        <FieldLabel htmlFor={`${fieldId}-key`}>
          {intl.formatMessage({
            id: "plugins_connection_key_label",
            defaultMessage: "API key",
          })}
        </FieldLabel>
        <Input
          id={`${fieldId}-key`}
          type="password"
          autoComplete="off"
          value={draft.key}
          onChange={(event) => change({ key: event.target.value })}
          placeholder={intl.formatMessage({
            id: "plugins_connection_key_placeholder",
            defaultMessage: "If the server asks for one",
          })}
          disabled={disabled}
        />
        <SendAsControl
          value={draft.sendAs}
          onChange={(sendAs) => change({ sendAs })}
          disabled={disabled}
        />
      </Field>
      {draft.sendAs === "custom" ? (
        <Field>
          <FieldLabel htmlFor={`${fieldId}-header`}>
            {intl.formatMessage({
              id: "plugins_connection_header_label",
              defaultMessage: "Header name",
            })}
          </FieldLabel>
          <Input
            id={`${fieldId}-header`}
            autoComplete="off"
            spellCheck={false}
            value={draft.headerName}
            onChange={(event) => change({ headerName: event.target.value })}
            placeholder="x-api-key"
            disabled={disabled}
          />
        </Field>
      ) : null}
      {draft.extra.length ? (
        <HeaderRows
          rows={draft.extra}
          onChange={(extra) => change({ extra })}
          disabled={disabled}
        />
      ) : (
        <div className="flex">
          <Button
            type="button"
            size="xs"
            variant="ghost"
            disabled={disabled}
            onClick={() => change({ extra: [{ name: "", value: "" }] })}
          >
            <PlusIcon data-icon="inline-start" />
            {intl.formatMessage({
              id: "plugins_connection_add_header_button",
              defaultMessage: "Add another header",
            })}
          </Button>
        </div>
      )}
    </>
  )
}
