import { useEffect, useState } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
  deleteConnection,
  getConnectionModels,
  setSelection,
  testConnectionImage,
  type Connection,
  type ConnectionModel,
  type ModelSelection,
} from "./api"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "The request failed"
}

function supportsImage(model: ConnectionModel) {
  return model.capabilities.includes("image_generation")
}

function supportsChat(model: ConnectionModel) {
  return model.capabilities.includes("completion")
}

export function ConnectionCard({
  connection,
  generationSelection,
  imageSelection,
  disabled,
  onEdit,
  onChanged,
  onGenerationUnavailable,
  onGenerationSelected,
}: {
  connection: Connection
  generationSelection: ModelSelection | null
  imageSelection: ModelSelection | null
  disabled: boolean
  onEdit: () => void
  onChanged: () => void
  onGenerationUnavailable?: () => void
  onGenerationSelected: (selection: ModelSelection) => void
}) {
  const [models, setModels] = useState<ConnectionModel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [manualName, setManualName] = useState("")
  const [disconnecting, setDisconnecting] = useState(false)
  const [imageModel, setImageModel] = useState<ConnectionModel | null>(null)
  const [imageBusy, setImageBusy] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [unlisted, setUnlisted] = useState<{
    role: ModelSelection["role"]
    model: ConnectionModel
    message: string
  } | null>(null)

  const loadModels = () => {
    const controller = new AbortController()
    void getConnectionModels(connection.id, controller.signal)
      .then(setModels)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }

  useEffect(() => {
    const controller = new AbortController()
    void getConnectionModels(connection.id, controller.signal)
      .then(setModels)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [connection.id])
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    },
    [previewUrl]
  )

  const selectable = (model: ConnectionModel) => ({
    ...model,
    provider: "openai_compatible",
    installed: true,
  })

  const assign = async (
    role: ModelSelection["role"],
    model: ConnectionModel,
    allowUnlisted = false
  ) => {
    setError(null)
    try {
      const selection = await setSelection(
        role,
        selectable(model),
        undefined,
        allowUnlisted
      )
      if (role === "generation") onGenerationSelected(selection)
      setImageModel(null)
      setUnlisted(null)
      onChanged()
    } catch (cause) {
      if (!allowUnlisted && cause instanceof ApiError && cause.status === 422) {
        setUnlisted({ role, model, message: messageFrom(cause) })
      } else {
        setError(messageFrom(cause))
      }
    }
  }

  const manualModel = (): ConnectionModel | null => {
    const name = manualName.trim()
    return name
      ? {
          connection_id: connection.id,
          connection_label: connection.label,
          name,
          capabilities: [],
          capability_known: false,
        }
      : null
  }

  const affectedRoles = [
    generationSelection?.connection_id === connection.id ? "Chat" : null,
    imageSelection?.connection_id === connection.id ? "Image" : null,
  ].filter(Boolean)

  return (
    <Card>
      <CardHeader className="gap-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="truncate">{connection.label}</CardTitle>
            <CardDescription className="truncate">
              {connection.base_url}
            </CardDescription>
          </div>
          <div className="flex gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={onEdit}
            >
              Edit
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                >
                  Disconnect
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    Disconnect {connection.label}?
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    {affectedRoles.length
                      ? `${affectedRoles.join(" and ")} role${affectedRoles.length > 1 ? "s" : ""} will be cleared.`
                      : "No assigned roles will be cleared."}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    variant="destructive"
                    disabled={disconnecting}
                    onClick={() => {
                      setDisconnecting(true)
                      void deleteConnection(connection.id)
                        .then(() => {
                          if (
                            generationSelection?.connection_id === connection.id
                          ) {
                            onGenerationUnavailable?.()
                          }
                          onChanged()
                        })
                        .catch((cause: unknown) => setError(messageFrom(cause)))
                        .finally(() => setDisconnecting(false))
                    }}
                  >
                    Disconnect
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner /> Loading models…
          </p>
        ) : error ? (
          <div className="space-y-2 text-sm">
            <p className="text-destructive">{error}</p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setLoading(true)
                setError(null)
                loadModels()
              }}
            >
              Retry
            </Button>
          </div>
        ) : models.length ? (
          <ul className="space-y-2">
            {models.map((model) => (
              <li
                key={`${connection.id}\0${model.name}`}
                className="flex flex-wrap items-center gap-2 rounded-md border p-2"
              >
                <div className="min-w-40 flex-1">
                  <p className="truncate text-sm font-medium">{model.name}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {model.capability_known ? (
                      model.capabilities.map((capability) => (
                        <Badge key={capability} variant="outline">
                          {capability.replaceAll("_", " ")}
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline">Capability unknown</Badge>
                    )}
                    {generationSelection?.connection_id === connection.id &&
                    generationSelection.name === model.name ? (
                      <Badge variant="secondary">Chat</Badge>
                    ) : null}
                    {imageSelection?.connection_id === connection.id &&
                    imageSelection.name === model.name ? (
                      <Badge variant="secondary">Image</Badge>
                    ) : null}
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={
                    disabled || (model.capability_known && !supportsChat(model))
                  }
                  onClick={() => void assign("generation", model)}
                >
                  Use for chat
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={
                    disabled ||
                    (model.capability_known && !supportsImage(model))
                  }
                  onClick={() =>
                    model.capability_known
                      ? void assign("image_generation", model)
                      : setImageModel(model)
                  }
                >
                  Assign as image
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No models were returned. Enter an exact model ID below.
          </p>
        )}

        <div className="flex gap-2">
          <Input
            value={manualName}
            onChange={(event) => setManualName(event.target.value)}
            placeholder="Manual model ID"
            aria-label={`Manual model ID for ${connection.label}`}
            disabled={disabled}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled || !manualName.trim()}
            onClick={() => {
              const model = manualModel()
              if (model) setUnlisted({ role: "generation", model, message: "" })
            }}
          >
            Use for chat
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled || !manualName.trim()}
            onClick={() => setImageModel(manualModel())}
          >
            Assign as image
          </Button>
        </div>
      </CardContent>

      <Dialog
        open={imageModel !== null}
        onOpenChange={(open) => {
          if (!open) {
            setImageModel(null)
            setPreviewUrl(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign {imageModel?.name} as Image?</DialogTitle>
            <DialogDescription>
              Capability is unknown. This endpoint must implement
              {" /images/generations "}or{" /images"}. Testing runs real
              inference and may cost money.
            </DialogDescription>
          </DialogHeader>
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={`Test generated by ${imageModel?.name}`}
              className="max-h-64 w-full rounded-md object-contain"
            />
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setImageModel(null)}>
              Cancel
            </Button>
            <Button
              variant="outline"
              disabled={imageBusy || !imageModel}
              onClick={() => {
                if (!imageModel) return
                setImageBusy(true)
                setError(null)
                void testConnectionImage(connection.id, imageModel.name)
                  .then((blob) => {
                    if (previewUrl) URL.revokeObjectURL(previewUrl)
                    setPreviewUrl(URL.createObjectURL(blob))
                  })
                  .catch((cause: unknown) => setError(messageFrom(cause)))
                  .finally(() => setImageBusy(false))
              }}
            >
              {imageBusy ? <Spinner data-icon="inline-start" /> : null}
              Test image
            </Button>
            <Button
              disabled={!imageModel}
              onClick={() =>
                imageModel && void assign("image_generation", imageModel, true)
              }
            >
              {previewUrl ? "Use for image" : "Use without testing"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={unlisted !== null}
        onOpenChange={(open) => !open && setUnlisted(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Use an unlisted model?</AlertDialogTitle>
            <AlertDialogDescription>
              {unlisted?.message ? `${unlisted.message} ` : ""}
              SurfSense could not confirm this model in the live catalogue.
              Continue only if the exact model ID is correct.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                unlisted && void assign(unlisted.role, unlisted.model, true)
              }
            >
              Use unlisted model
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  )
}
