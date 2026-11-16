import { useId, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { ChevronDownIcon, ChevronRightIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"

import { CallbackAddress } from "./callback-address"
import type { OwnAppDraft } from "./own-app-draft"

function Step({
  number,
  title,
  children,
}: {
  number: number
  title: string
  children: ReactNode
}) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden
        className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground tabular-nums"
      >
        {intl.formatNumber(number)}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <p className="text-sm font-medium">{title}</p>
        {children}
      </div>
    </li>
  )
}

/**
 * The user's own OAuth app, as the three steps it takes: register an app with the provider,
 * give it SurfSense's callback, paste what it gives. Most of it happens outside SurfSense.
 */
export function OwnAppFields({
  provider,
  value,
  onChange,
  redirectUri,
  disabled = false,
}: {
  /** The plugin or provider, as the steps name it. */
  provider: string
  value: OwnAppDraft
  onChange: (value: OwnAppDraft) => void
  /** Null while the API has not said which callback this build signs in with. */
  redirectUri: string | null
  disabled?: boolean
}) {
  const fieldId = useId()
  // Most providers take scopes from the server; a wrong one breaks the sign-in.
  const [scopesOpen, setScopesOpen] = useState(value.scopes !== "")
  const change = (part: Partial<OwnAppDraft>) => onChange({ ...value, ...part })
  return (
    <ol className="flex flex-col gap-5">
      <Step
        number={1}
        title={intl.formatMessage(
          {
            id: "plugins_own_app_register_title",
            defaultMessage: "Register an OAuth app with {provider}",
          },
          { provider }
        )}
      >
        <p className="text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_own_app_register_body",
            defaultMessage:
              "In its developer settings, create a new OAuth app.",
          })}
        </p>
      </Step>
      <Step
        number={2}
        title={intl.formatMessage({
          id: "plugins_own_app_callback_title",
          defaultMessage: "Give it this callback address",
        })}
      >
        <CallbackAddress id={`${fieldId}-callback`} address={redirectUri} />
      </Step>
      <Step
        number={3}
        title={intl.formatMessage(
          {
            id: "plugins_own_app_paste_title",
            defaultMessage: "Paste what {provider} gives you",
          },
          { provider }
        )}
      >
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
        <div className="flex">
          <Button
            type="button"
            size="xs"
            variant="ghost"
            className="-ml-2"
            aria-expanded={scopesOpen}
            disabled={disabled}
            onClick={() => setScopesOpen(!scopesOpen)}
          >
            {scopesOpen ? (
              <ChevronDownIcon data-icon="inline-start" />
            ) : (
              <ChevronRightIcon data-icon="inline-start" />
            )}
            {intl.formatMessage({
              id: "plugins_own_app_scopes_toggle_button",
              defaultMessage: "Scopes",
            })}
          </Button>
        </div>
        {scopesOpen ? (
          <Field>
            <FieldLabel htmlFor={`${fieldId}-scopes`} className="sr-only">
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
              placeholder={intl.formatMessage(
                {
                  id: "plugins_own_app_scopes_hint_placeholder",
                  defaultMessage:
                    "Only if {provider} asks for some, separated by spaces",
                },
                { provider }
              )}
              disabled={disabled}
            />
          </Field>
        ) : null}
      </Step>
    </ol>
  )
}
