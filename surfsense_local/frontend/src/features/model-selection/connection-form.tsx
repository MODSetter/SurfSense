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
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { ApiError } from "@/lib/api"

import {
  createConnection,
  updateConnection,
  type Connection,
  type ConnectionWrite,
} from "./api"

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
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {connection ? "Edit connection" : "Add connection"}
          </DialogTitle>
          <DialogDescription>
            Connect an endpoint that implements the OpenAI API.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Input
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Engineering vLLM"
            aria-label="Connection label"
            disabled={busy}
          />
          <Input
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="https://models.example.com/v1"
            aria-label="Base URL"
            disabled={busy}
          />
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
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={clearKey}
                onCheckedChange={(checked) => setClearKey(checked === true)}
                disabled={busy || Boolean(apiKey)}
              />
              Remove saved API key
            </label>
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
