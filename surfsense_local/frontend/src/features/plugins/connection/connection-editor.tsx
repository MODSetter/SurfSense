import { useId } from "react"

import { Button } from "@/components/ui/button"
import { Field, FieldLabel, FieldSeparator } from "@/components/ui/field"
import { PlusIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"

import { HeaderRows } from "../headers/header-rows"
import { OwnAppFields } from "../sign-in/own-app/own-app-fields"
import type { ConnectionDraft } from "./connection-draft"
import { SendAsControl } from "./send-as-control"

/**
 * How a plugin's server is reached once it asks for something: a key and how it is sent,
 * further headers, and, for an OAuth provider taking only registered apps, the user's own.
 * The same fields in Add custom plugin and in Edit connection.
 */
export function ConnectionEditor({
  draft,
  onChange,
  withOAuth,
  redirectUri,
  disabled,
}: {
  draft: ConnectionDraft
  onChange: (draft: ConnectionDraft) => void
  // The OAuth app fields, where a sign-in may need them.
  withOAuth: boolean
  redirectUri: string | null
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
      {withOAuth ? (
        <>
          <FieldSeparator />
          <OwnAppFields
            value={draft.ownApp}
            onChange={(ownApp) => change({ ownApp })}
            redirectUri={redirectUri}
            disabled={disabled}
          />
        </>
      ) : null}
    </>
  )
}
