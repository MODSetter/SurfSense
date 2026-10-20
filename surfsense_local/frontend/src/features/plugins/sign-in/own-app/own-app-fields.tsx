import { useId } from "react"

import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"

import type { OwnAppDraft } from "./own-app-draft"

/** The user's own OAuth app: the callback to register it with, then what the provider gave. */
export function OwnAppFields({
  value,
  onChange,
  redirectUri,
  disabled = false,
}: {
  value: OwnAppDraft
  onChange: (value: OwnAppDraft) => void
  /** Null while the API has not said which callback this build signs in with. */
  redirectUri: string | null
  disabled?: boolean
}) {
  const fieldId = useId()
  const change = (part: Partial<OwnAppDraft>) => onChange({ ...value, ...part })
  return (
    <>
      <Field>
        <FieldLabel htmlFor={`${fieldId}-callback`}>
          {intl.formatMessage({
            id: "plugins_own_app_callback_label",
            defaultMessage: "Callback address",
          })}
        </FieldLabel>
        <Input
          id={`${fieldId}-callback`}
          readOnly
          value={redirectUri ?? ""}
          className="font-mono text-xs select-text"
          onFocus={(event) => event.currentTarget.select()}
        />
        <FieldDescription>
          {intl.formatMessage({
            id: "plugins_own_app_callback_body",
            defaultMessage:
              "Register an OAuth app with the provider using this callback address, then enter what it gives you.",
          })}
        </FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor={`${fieldId}-client`}>
          {intl.formatMessage({
            id: "plugins_own_app_client_label",
            defaultMessage: "Client ID",
          })}
        </FieldLabel>
        <Input
          id={`${fieldId}-client`}
          autoComplete="off"
          spellCheck={false}
          value={value.clientId}
          onChange={(event) => change({ clientId: event.target.value })}
          disabled={disabled}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor={`${fieldId}-secret`}>
          {intl.formatMessage({
            id: "plugins_own_app_credential_label",
            defaultMessage: "Client secret",
          })}
        </FieldLabel>
        <Input
          id={`${fieldId}-secret`}
          type="password"
          autoComplete="off"
          value={value.clientSecret}
          onChange={(event) => change({ clientSecret: event.target.value })}
          placeholder={intl.formatMessage({
            id: "plugins_own_app_credential_placeholder",
            defaultMessage: "If the provider gave one",
          })}
          disabled={disabled}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor={`${fieldId}-scopes`}>
          {intl.formatMessage({
            id: "plugins_own_app_scopes_label",
            defaultMessage: "Scopes",
          })}
        </FieldLabel>
        <Input
          id={`${fieldId}-scopes`}
          autoComplete="off"
          spellCheck={false}
          value={value.scopes}
          onChange={(event) => change({ scopes: event.target.value })}
          placeholder={intl.formatMessage({
            id: "plugins_own_app_scopes_placeholder",
            defaultMessage: "Optional, separated by spaces",
          })}
          disabled={disabled}
        />
      </Field>
    </>
  )
}
