import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
} from "@/components/ui/combobox"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { ApiError } from "@/lib/api"

import {
  createConnection,
  updateConnection,
  type Connection,
  type ConnectionWrite,
} from "./api"

const COMMON_BASE_URLS = [
  { name: "OpenAI", url: "https://api.openai.com/v1" },
  { name: "OpenRouter", url: "https://openrouter.ai/api/v1" },
  { name: "Together AI", url: "https://api.together.xyz/v1" },
  { name: "Groq", url: "https://api.groq.com/openai/v1" },
  { name: "DeepSeek", url: "https://api.deepseek.com/v1" },
  { name: "Mistral", url: "https://api.mistral.ai/v1" },
  { name: "Fireworks", url: "https://api.fireworks.ai/inference/v1" },
  { name: "xAI", url: "https://api.x.ai/v1" },
  { name: "Cerebras", url: "https://api.cerebras.ai/v1" },
  {
    name: "Google Gemini",
    url: "https://generativelanguage.googleapis.com/v1beta/openai",
  },
  { name: "Ollama (local)", url: "http://localhost:11434/v1" },
  { name: "LM Studio (local)", url: "http://localhost:1234/v1" },
  { name: "vLLM (local)", url: "http://localhost:8000/v1" },
] as const

function presetFor(url: string) {
  return COMMON_BASE_URLS.find((entry) => entry.url === url)
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not save connection"
}

export function ConnectionForm({
  open,
  connection,
  onOpenChange,
  onSaved,
}: {
  open: boolean
  connection?: Connection
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [label, setLabel] = useState(connection?.label ?? "")
  const [baseUrl, setBaseUrl] = useState(connection?.base_url ?? "")
  const [apiKey, setApiKey] = useState("")
  const [clearKey, setClearKey] = useState(false)
  const [busy, setBusy] = useState(false)
  const [verificationError, setVerificationError] = useState<string | null>(
    null
  )
  const [canSaveAnyway, setCanSaveAnyway] = useState(false)
  // Hosts the combobox popup inside the dialog so the dialog's scroll lock
  // lets the list scroll. Absolute, so it adds no height and the dialog, which
  // is centred by transform, does not shift when the popup opens.
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
      ...(clearKey ? { api_key: null } : apiKey ? { api_key: apiKey } : {}),
    }
    try {
      if (connection) {
        await updateConnection(connection.id, body)
      } else {
        await createConnection(body)
      }
      onSaved()
      onOpenChange(false)
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="select-none">
        <DialogHeader>
          <DialogTitle>
            {connection ? "Edit connection" : "Add connection"}
          </DialogTitle>
          <DialogDescription>
            Connect an endpoint that implements the OpenAI API.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div ref={setPopupHost} className="absolute" />
          <Input
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Engineering vLLM"
            aria-label="Connection label"
            disabled={busy}
          />
          <Combobox
            value={baseUrl}
            onValueChange={(url) => {
              const preset = presetFor(url)
              if (preset && !label.trim()) setLabel(preset.name)
            }}
            inputValue={baseUrl}
            onInputValueChange={setBaseUrl}
            disabled={busy}
          >
            <ComboboxInput
              placeholder="https://models.example.com/v1"
              aria-label="Base URL"
            />
            <ComboboxContent container={popupHost}>
              <ComboboxEmpty>No items found</ComboboxEmpty>
              <ComboboxList>
                <ComboboxGroup>
                  <ComboboxLabel>Common endpoints</ComboboxLabel>
                  {COMMON_BASE_URLS.map((entry) => (
                    <ComboboxItem
                      key={entry.url}
                      value={entry.url}
                      keywords={[entry.name]}
                    >
                      <span className="min-w-0 flex-1 truncate">
                        {entry.name}
                        <span className="ml-1.5 text-muted-foreground">
                          {entry.url}
                        </span>
                      </span>
                    </ComboboxItem>
                  ))}
                </ComboboxGroup>
              </ComboboxList>
            </ComboboxContent>
          </Combobox>
          <Input
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={
              connection?.has_api_key
                ? "Leave blank to keep the saved key"
                : "API key (optional)"
            }
            aria-label="API key"
            disabled={busy}
          />
          {connection?.has_api_key ? (
            <Field orientation="horizontal">
              <Checkbox
                id={`clear-key-${connection.id}`}
                checked={clearKey}
                onCheckedChange={(checked) => setClearKey(checked === true)}
                disabled={busy || Boolean(apiKey)}
              />
              <FieldLabel htmlFor={`clear-key-${connection.id}`}>
                Remove saved API key
              </FieldLabel>
            </Field>
          ) : null}
          {verificationError ? (
            <div className="space-y-2 text-sm" role="alert">
              <p className="text-destructive">{verificationError}</p>
              {canSaveAnyway ? (
                <>
                  <p className="text-muted-foreground">
                    Save anyway only if you trust this endpoint. You will enter
                    model IDs manually.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void save(true)}
                  >
                    Save anyway
                  </Button>
                </>
              ) : null}
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={busy || !label.trim() || !baseUrl.trim()}
            onClick={() => void save(false)}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}
            Save connection
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
