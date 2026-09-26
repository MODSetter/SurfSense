import { useQuery } from "@tanstack/react-query"
import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Combobox,
  ComboboxCollection,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
} from "@/components/ui/combobox"
import { DialogFooter } from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { ApiError } from "@/lib/api"
import { intl } from "@/i18n/intl"

import {
  CUSTOM_PROVIDER,
  createConnection,
  getRemoteProviders,
  updateConnection,
  type Connection,
  type ConnectionWrite,
  type RemoteProvider,
} from "./api"
import { fillTemplate } from "./provider-url"

// A local server's port is whatever its owner set, so nothing is filled in:
// this is an example, shown as placeholder text only.
const CUSTOM_PLACEHOLDER = "http://localhost:11434/v1"

type ProviderOption = {
  value: string
  label: string
  hint: string | null
  keywords: string[]
  disabled: boolean
}

type ProviderGroup = { label: string | null; items: ProviderOption[] }

// Matches the id as well as the name, so "bedrock" finds Amazon Bedrock.
function matchesProvider(option: ProviderOption, query: string) {
  const needle = query.trim().toLowerCase()
  return [option.label, ...option.keywords].some((candidate) =>
    candidate.toLowerCase().includes(needle)
  )
}

function urlHint(provider: RemoteProvider) {
  const { connect } = provider
  if (connect.status === "unreachable") return connect.reason
  if (connect.status === "needs_account_details")
    return intl.formatMessage({
      id: "models_connection_form_provider_needs_account_body",
      defaultMessage: "Needs your account details",
    })
  if (connect.status === "needs_url")
    return intl.formatMessage({
      id: "models_connection_form_provider_needs_url_body",
      defaultMessage: "Enter its URL",
    })
  return connect.base_url
}

function messageFrom(error: unknown) {
  if (error instanceof ApiError && error.code === "unverified_connection") {
    return intl.formatMessage({
      id: "models_error_unverified_connection",
      defaultMessage: "The endpoint’s model list could not be verified.",
    })
  }
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_connection_form_save_error",
        defaultMessage: "Could not save connection",
      })
}

/**
 * Adds a server, or edits one when `connection` is given. The body of
 * `ConnectionDialog`, laid out like the app's other form dialogs: labelled
 * fields, then the actions in the dialog's footer.
 */
export function ConnectionForm({
  connection,
  onCancel,
  onSaved,
}: {
  connection?: Connection
  onCancel: () => void
  onSaved: (connection: Connection) => void
}) {
  const fieldId = useId()
  const customLabel = intl.formatMessage({
    id: "models_connection_form_custom_provider_label",
    defaultMessage: "Local or custom server",
  })
  const [label, setLabel] = useState(connection?.label ?? "")
  const [baseUrl, setBaseUrl] = useState(connection?.base_url ?? "")
  const [providerId, setProviderId] = useState(
    connection?.catalog_provider ?? CUSTOM_PROVIDER
  )
  const [accountValues, setAccountValues] = useState<Record<string, string>>({})
  const providers = useQuery({
    queryKey: ["remote-providers"],
    queryFn: ({ signal }) => getRemoteProviders(signal),
    staleTime: Infinity,
  })
  const sortedProviders = (providers.data ?? []).toSorted((left, right) =>
    left.name.localeCompare(right.name)
  )
  const chosen = sortedProviders.find((entry) => entry.id === providerId)

  const customOption: ProviderOption = {
    value: CUSTOM_PROVIDER,
    label: customLabel,
    hint: intl.formatMessage({
      id: "models_connection_form_custom_provider_body",
      defaultMessage: "Any OpenAI-compatible URL",
    }),
    keywords: ["local", "custom"],
    disabled: false,
  }
  const providerGroups: ProviderGroup[] = [
    { label: null, items: [customOption] },
    {
      label: intl.formatMessage({
        id: "models_connection_form_providers_label",
        defaultMessage: "Providers",
      }),
      items: sortedProviders.map((entry) => ({
        value: entry.id,
        label: entry.name,
        hint: urlHint(entry),
        keywords: [entry.id],
        disabled: entry.connect.status === "unreachable",
      })),
    },
  ]
  const selectedOption =
    providerGroups[1].items.find((option) => option.value === providerId) ??
    customOption

  const choose = (option: ProviderOption | null) => {
    if (!option) return
    setAccountValues({})
    if (option.value === CUSTOM_PROVIDER) {
      setProviderId(CUSTOM_PROVIDER)
      setBaseUrl("")
      return
    }
    const next = sortedProviders.find((entry) => entry.id === option.value)
    if (!next || next.connect.status === "unreachable") return
    setProviderId(next.id)
    setBaseUrl(
      next.connect.status === "ready" ? (next.connect.base_url ?? "") : ""
    )
    if (!label.trim()) setLabel(next.name)
  }

  const setAccountValue = (name: string, value: string) => {
    const next = { ...accountValues, [name]: value }
    setAccountValues(next)
    if (chosen?.connect.base_url) {
      setBaseUrl(fillTemplate(chosen.connect.base_url, next))
    }
  }
  const [apiKey, setApiKey] = useState("")
  const [clearKey, setClearKey] = useState(false)
  const [busy, setBusy] = useState(false)
  const [verificationError, setVerificationError] = useState<string | null>(
    null
  )
  const [canSaveAnyway, setCanSaveAnyway] = useState(false)
  // Hosts the combobox popup inside the settings dialog, which hides
  // everything outside itself from assistive technology. Absolute, so it adds
  // no height and the centred dialog does not shift when the popup opens.
  const [popupHost, setPopupHost] = useState<HTMLDivElement | null>(null)

  const save = async (allowUnverified: boolean) => {
    setBusy(true)
    setVerificationError(null)
    setCanSaveAnyway(false)
    const body: ConnectionWrite = {
      label: label.trim(),
      provider: "openai_compatible",
      base_url: baseUrl.trim(),
      allow_unverified: allowUnverified,
      catalog_provider: providerId,
      ...(clearKey ? { api_key: null } : apiKey ? { api_key: apiKey } : {}),
    }
    try {
      onSaved(
        connection
          ? await updateConnection(connection.id, body)
          : await createConnection(body)
      )
    } catch (error) {
      setVerificationError(messageFrom(error))
      setCanSaveAnyway(
        error instanceof ApiError && error.code === "unverified_connection"
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <FieldGroup className="relative">
        <div ref={setPopupHost} className="absolute" />
        <Field>
          <FieldLabel htmlFor={`${fieldId}-name`}>
            {intl.formatMessage({
              id: "models_connection_form_name_label",
              defaultMessage: "Name",
            })}
          </FieldLabel>
          <Input
            id={`${fieldId}-name`}
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder={intl.formatMessage({
              id: "models_connection_form_name_placeholder",
              defaultMessage: "Engineering vLLM",
            })}
            disabled={busy}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={`${fieldId}-provider`}>
            {intl.formatMessage({
              id: "models_connection_form_provider_label",
              defaultMessage: "Provider",
            })}
          </FieldLabel>
          <Combobox
            items={providerGroups}
            value={selectedOption}
            onValueChange={choose}
            isItemEqualToValue={(item, value) => item.value === value.value}
            filter={matchesProvider}
            disabled={busy}
          >
            <ComboboxInput
              id={`${fieldId}-provider`}
              disabled={busy}
              placeholder={intl.formatMessage({
                id: "models_connection_form_provider_placeholder",
                defaultMessage: "Search providers",
              })}
            />
            <ComboboxContent container={popupHost}>
              <ComboboxEmpty>
                {intl.formatMessage({
                  id: "models_connection_form_provider_empty",
                  defaultMessage: "No provider found",
                })}
              </ComboboxEmpty>
              <ComboboxList>
                {(group: ProviderGroup) => (
                  <ComboboxGroup
                    key={group.label ?? "custom"}
                    items={group.items}
                  >
                    {group.label ? (
                      <ComboboxLabel>{group.label}</ComboboxLabel>
                    ) : null}
                    <ComboboxCollection>
                      {(option: ProviderOption) => (
                        <ComboboxItem
                          key={option.value}
                          value={option}
                          disabled={option.disabled}
                        >
                          <span className="min-w-0 flex-1 truncate">
                            {option.label}
                            <span className="ml-1.5 text-muted-foreground">
                              {option.hint}
                            </span>
                          </span>
                        </ComboboxItem>
                      )}
                    </ComboboxCollection>
                  </ComboboxGroup>
                )}
              </ComboboxList>
            </ComboboxContent>
          </Combobox>
        </Field>
        {chosen?.connect.status === "needs_account_details"
          ? chosen.connect.account_fields.map((field) => (
              <Field key={field.name}>
                <FieldLabel htmlFor={`${fieldId}-${field.name}`}>
                  {field.label}
                </FieldLabel>
                <Input
                  id={`${fieldId}-${field.name}`}
                  value={accountValues[field.name] ?? ""}
                  onChange={(event) =>
                    setAccountValue(field.name, event.target.value)
                  }
                  disabled={busy}
                />
              </Field>
            ))
          : null}
        <Field>
          <FieldLabel htmlFor={`${fieldId}-url`}>
            {intl.formatMessage({
              id: "models_connection_form_url_label",
              defaultMessage: "Base URL",
            })}
          </FieldLabel>
          <Input
            id={`${fieldId}-url`}
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder={
              chosen
                ? intl.formatMessage(
                    {
                      id: "models_connection_form_url_provider_placeholder",
                      defaultMessage: "{provider} API URL",
                    },
                    {
                      provider: chosen.name,
                    }
                  )
                : intl.formatMessage(
                    {
                      id: "models_connection_form_url_custom_placeholder",
                      defaultMessage: "e.g. {url}",
                    },
                    {
                      url: CUSTOM_PLACEHOLDER,
                    }
                  )
            }
            disabled={busy}
          />
        </Field>
        {chosen?.connect.key === "none" ? null : (
          <Field>
            <FieldLabel htmlFor={`${fieldId}-key`}>
              {intl.formatMessage({
                id: "models_connection_form_key_label",
                defaultMessage: "API key",
              })}
            </FieldLabel>
            <Input
              id={`${fieldId}-key`}
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                connection?.has_api_key
                  ? intl.formatMessage({
                      id: "models_connection_form_key_saved_placeholder",
                      defaultMessage: "Leave blank to keep the saved key",
                    })
                  : intl.formatMessage({
                      id: "models_connection_form_key_placeholder",
                      defaultMessage: "Optional",
                    })
              }
              disabled={busy}
            />
          </Field>
        )}
        {connection?.has_api_key ? (
          <Field orientation="horizontal">
            <Checkbox
              id={`${fieldId}-clear-key`}
              checked={clearKey}
              onCheckedChange={(checked) => setClearKey(checked === true)}
              disabled={busy || Boolean(apiKey)}
            />
            <FieldLabel htmlFor={`${fieldId}-clear-key`}>
              {intl.formatMessage({
                id: "models_connection_form_clear_key_label",
                defaultMessage: "Remove saved API key",
              })}
            </FieldLabel>
          </Field>
        ) : null}
        {verificationError ? (
          <div className="flex flex-col gap-2 text-sm" role="alert">
            <p className="text-destructive">{verificationError}</p>
            {canSaveAnyway ? (
              <>
                <p className="text-muted-foreground">
                  {intl.formatMessage({
                    id: "models_connection_form_save_anyway_body",
                    defaultMessage:
                      "Save anyway only if you trust this endpoint. You will enter model IDs manually.",
                  })}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  className="self-start"
                  disabled={busy}
                  onClick={() => void save(true)}
                >
                  {intl.formatMessage({
                    id: "models_connection_form_save_anyway_button",
                    defaultMessage: "Save anyway",
                  })}
                </Button>
              </>
            ) : null}
          </div>
        ) : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "models_connection_form_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button
          type="button"
          disabled={busy || !label.trim() || !baseUrl.trim()}
          onClick={() => void save(false)}
        >
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {connection
            ? intl.formatMessage({
                id: "models_connection_form_save_changes_button",
                defaultMessage: "Save changes",
              })
            : intl.formatMessage({
                id: "models_connection_form_save_button",
                defaultMessage: "Save server",
              })}
        </Button>
      </DialogFooter>
    </>
  )
}
