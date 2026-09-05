import { useState } from "react"

import { CheckIcon, CircleAlertIcon, KeyRoundIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"

import { type Provider, type SelectableModel } from "../../api"
import { ModelList } from "../../model-list"
import { clearProviderCredential, setProviderCredential } from "./api"

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

export function OpenRouterPanel({
  provider,
  models,
  draftKey,
  persistedKey,
  onSelect,
  disabled,
  onChanged,
}: {
  provider: Provider
  models: SelectableModel[]
  draftKey: string | null
  persistedKey: string | null
  onSelect: (key: string) => void
  disabled: boolean
  onChanged: () => Promise<void>
}) {
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connect = async () => {
    const trimmed = key.trim()
    if (!trimmed) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      await setProviderCredential(provider.name, trimmed)
      setKey("")
      await onChanged()
    } catch (unknownError) {
      setError(messageFrom(unknownError, "Could not save the API key"))
    } finally {
      setBusy(false)
    }
  }

  const disconnect = async () => {
    setBusy(true)
    setError(null)
    try {
      await clearProviderCredential(provider.name)
      await onChanged()
    } catch (unknownError) {
      setError(messageFrom(unknownError, "Could not remove the API key"))
    } finally {
      setBusy(false)
    }
  }

  if (provider.configured && provider.healthy) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <CheckIcon className="size-4" />
            Connected with your API key
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => void disconnect()}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}
            Disconnect
          </Button>
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <ModelList
          models={models}
          draftKey={draftKey}
          persistedKey={persistedKey}
          onSelect={onSelect}
          disabled={disabled}
          searchable
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-medium">
          Use remote models with your OpenRouter key
        </h2>
        <p className="text-sm text-pretty text-muted-foreground">
          Bring your own key to run capable models we can&apos;t host locally.
          The key is stored on this machine only.
        </p>
      </div>

      {provider.configured && !provider.healthy ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>OpenRouter isn&apos;t responding</AlertTitle>
          <AlertDescription>
            Your saved key may be invalid or expired. Enter a new one, or
            disconnect.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex items-start gap-2">
        <Input
          type="password"
          autoComplete="off"
          placeholder="sk-or-..."
          value={key}
          onChange={(event) => setKey(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void connect()
            }
          }}
          disabled={busy}
          aria-label="OpenRouter API key"
        />
        <Button
          type="button"
          disabled={busy || key.trim() === ""}
          onClick={() => void connect()}
        >
          {busy ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <KeyRoundIcon data-icon="inline-start" />
          )}
          Connect
        </Button>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {provider.configured && !provider.healthy ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="self-start"
          disabled={busy}
          onClick={() => void disconnect()}
        >
          Disconnect
        </Button>
      ) : null}
    </div>
  )
}
