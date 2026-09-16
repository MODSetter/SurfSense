import { useEffect, useMemo, useRef, useState } from "react"

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
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { SearchIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ApiError } from "@/lib/api"

import {
  deleteConnection,
  getConnectionModels,
  setSelection,
  testConnectionChat,
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

function capabilityBadge(capability: string) {
  if (capability === "completion") {
    return { label: "Completion", variant: "secondary" } as const
  }
  if (capability === "image_generation") {
    return { label: "Image Generation", variant: "secondary" } as const
  }
  return { label: capability, variant: "outline" } as const
}

type ModelFilter = "all" | "chat" | "image" | "unknown"

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
  const [models, setModels] = useState<ConnectionModel[] | null>(null)
  const [browserOpen, setBrowserOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manualName, setManualName] = useState("")
  const [search, setSearch] = useState("")
  const [filter, setFilter] = useState<ModelFilter>("all")
  const [disconnecting, setDisconnecting] = useState(false)
  // A model awaiting a role, which it can be asked to prove it fills first.
  // `unlisted` is set only for a hand-typed id, so a model the connection did
  // list still goes through the server's own check.
  const [trying, setTrying] = useState<{
    role: ModelSelection["role"]
    model: ConnectionModel
    unlisted?: boolean
  } | null>(null)
  const [testBusy, setTestBusy] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [reply, setReply] = useState<string | null>(null)
  const [unlisted, setUnlisted] = useState<{
    role: ModelSelection["role"]
    model: ConnectionModel
    message: string
  } | null>(null)
  const modelsRequest = useRef<AbortController | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const loadModels = () => {
    modelsRequest.current?.abort()
    const controller = new AbortController()
    modelsRequest.current = controller
    setLoading(true)
    setError(null)
    void getConnectionModels(connection.id, controller.signal)
      .then(setModels)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }

  useEffect(() => () => modelsRequest.current?.abort(), [])
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
      setTrying(null)
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

  const runTest = () => {
    if (!trying) return
    const { role, model } = trying
    setTestBusy(true)
    setError(null)
    const attempt =
      role === "image_generation"
        ? testConnectionImage(connection.id, model.name).then((blob) => {
            if (previewUrl) URL.revokeObjectURL(previewUrl)
            setPreviewUrl(URL.createObjectURL(blob))
          })
        : testConnectionChat(connection.id, model.name).then(setReply)
    void attempt
      .catch((cause: unknown) => setError(messageFrom(cause)))
      .finally(() => setTestBusy(false))
  }

  const manualModel = (): ConnectionModel | null => {
    const name = manualName.trim()
    return name
      ? {
          connection_id: connection.id,
          connection_label: connection.label,
          name,
          capabilities: [],
          capability_source: "unknown",
        }
      : null
  }

  const affectedRoles = [
    generationSelection?.connection_id === connection.id ? "Chat" : null,
    imageSelection?.connection_id === connection.id ? "Image" : null,
  ].filter(Boolean)
  const generationName =
    generationSelection?.connection_id === connection.id
      ? generationSelection.name
      : null
  const imageName =
    imageSelection?.connection_id === connection.id ? imageSelection.name : null
  const filteredModels = useMemo(() => {
    if (!models) return []
    const query = search.trim().toLocaleLowerCase()
    return models.filter((model) => {
      if (!model.name.toLocaleLowerCase().includes(query)) return false
      if (filter === "chat") return supportsChat(model)
      if (filter === "image") return supportsImage(model)
      if (filter === "unknown") return model.capability_source === "unknown"
      return true
    })
  }, [filter, models, search])

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
          <div className="flex shrink-0 flex-wrap justify-end gap-1">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={disabled}
              onClick={() => {
                setBrowserOpen(true)
                if (models === null && !loading) loadModels()
              }}
            >
              Browse models
            </Button>
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
                  variant="destructive"
                  size="sm"
                  disabled={disabled}
                >
                  Disconnect
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="select-none">
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
      {error && !browserOpen ? (
        <CardContent>
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        </CardContent>
      ) : null}

      <Dialog
        open={browserOpen}
        onOpenChange={(open) => {
          setBrowserOpen(open)
          if (open && models === null && !loading) loadModels()
        }}
      >
        <DialogContent
          className="flex h-[85svh] max-h-[44rem] flex-col gap-0 overflow-hidden select-none sm:max-w-3xl"
          onOpenAutoFocus={(event) => {
            event.preventDefault()
            searchRef.current?.focus()
          }}
        >
          <DialogHeader>
            <DialogTitle>Browse models</DialogTitle>
            <DialogDescription className="truncate">
              {connection.label}
            </DialogDescription>
          </DialogHeader>

          <Field className="mt-4">
            <FieldLabel htmlFor={`manual-model-${connection.id}`}>
              Exact model ID
            </FieldLabel>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id={`manual-model-${connection.id}`}
                value={manualName}
                onChange={(event) => setManualName(event.target.value)}
                placeholder="provider/model-id"
                disabled={disabled}
              />
              <Button
                type="button"
                size="sm"
                disabled={disabled || !manualName.trim()}
                onClick={() => {
                  const model = manualModel()
                  if (model) {
                    setTrying({
                      role: "image_generation",
                      model,
                      unlisted: true,
                    })
                  }
                }}
              >
                Assign as image
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={disabled || !manualName.trim()}
                onClick={() => {
                  const model = manualModel()
                  if (model) {
                    setTrying({ role: "generation", model, unlisted: true })
                  }
                }}
              >
                Use for chat
              </Button>
            </div>
            <FieldDescription>
              If a model is missing from the list, type its ID and assign it.
            </FieldDescription>
          </Field>

          <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3 border-t pt-4">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                ref={searchRef}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search available models"
                aria-label={`Search models from ${connection.label}`}
                className="pl-9"
              />
            </div>
            <Tabs
              value={filter}
              onValueChange={(value) => setFilter(value as ModelFilter)}
            >
              <TabsList className="w-full sm:w-fit">
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="chat">Chat</TabsTrigger>
                <TabsTrigger value="image">Image</TabsTrigger>
                <TabsTrigger value="unknown">Unknown</TabsTrigger>
              </TabsList>
            </Tabs>

            {loading ? (
              <p
                className="flex items-center gap-2 py-8 text-sm text-muted-foreground"
                role="status"
                aria-label="Loading models"
              >
                <Spinner /> Loading models…
              </p>
            ) : error ? (
              <div className="flex flex-col items-start gap-2 py-4 text-sm">
                <p className="text-destructive" role="alert">
                  {error}
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={loadModels}
                >
                  Retry
                </Button>
              </div>
            ) : filteredModels.length ? (
              <ScrollShadow className="flex-1" viewportClassName="pr-1">
                <ul className="divide-y pb-1">
                  {filteredModels.map((model) => (
                    <li
                      key={`${connection.id}\0${model.name}`}
                      className="flex flex-wrap items-center content-start gap-2 py-2"
                    >
                      <div className="min-w-40 flex-1">
                        <p className="truncate text-sm font-medium">
                          {model.name}
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {model.capability_source === "unknown" ? (
                            <Badge variant="outline">Capability unknown</Badge>
                          ) : (
                            model.capabilities.map((capability) => {
                              const badge = capabilityBadge(capability)
                              const guessed =
                                model.capability_source === "inferred"
                              return (
                                <Badge
                                  key={capability}
                                  variant={guessed ? "outline" : badge.variant}
                                  title={
                                    guessed
                                      ? `${connection.label} does not publish capabilities; this was read from the model name.`
                                      : undefined
                                  }
                                >
                                  {guessed
                                    ? `${badge.label}?`
                                    : badge.label}
                                </Badge>
                              )
                            })
                          )}
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant={
                          imageName === model.name ? "outline" : "default"
                        }
                        aria-label={
                          imageName === model.name
                            ? "In use for image"
                            : "Assign as image"
                        }
                        disabled={
                          disabled ||
                          imageName === model.name ||
                          (model.capability_source !== "unknown" &&
                            !supportsImage(model))
                        }
                        onClick={() =>
                          model.capability_source === "declared"
                            ? void assign("image_generation", model)
                            : setTrying({ role: "image_generation", model })
                        }
                      >
                        {imageName === model.name
                          ? "In use"
                          : "Assign as image"}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant={
                          generationName === model.name ? "outline" : "default"
                        }
                        aria-label={
                          generationName === model.name
                            ? "In use for chat"
                            : "Use for chat"
                        }
                        disabled={
                          disabled ||
                          generationName === model.name ||
                          (model.capability_source !== "unknown" &&
                            !supportsChat(model))
                        }
                        onClick={() =>
                          model.capability_source === "declared"
                            ? void assign("generation", model)
                            : setTrying({ role: "generation", model })
                        }
                      >
                        {generationName === model.name
                          ? "In use"
                          : "Use for chat"}
                      </Button>
                    </li>
                  ))}
                </ul>
              </ScrollShadow>
            ) : (
              <Empty className="mb-4 min-h-40 border">
                <EmptyHeader>
                  <EmptyTitle>
                    {models?.length
                      ? "No matching models"
                      : "No models returned"}
                  </EmptyTitle>
                  <EmptyDescription>
                    {models?.length
                      ? "Try another search or capability filter."
                      : "Enter an exact model ID above."}
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
          </div>
          <DialogFooter showCloseButton />
        </DialogContent>
      </Dialog>

      <Dialog
        open={trying !== null}
        onOpenChange={(open) => {
          if (!open) {
            setTrying(null)
            setPreviewUrl(null)
            setReply(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {trying?.role === "image_generation"
                ? `Assign ${trying?.model.name} as Image?`
                : `Use ${trying?.model.name} for chat?`}
            </DialogTitle>
            <DialogDescription>
              {trying?.role === "image_generation" ? (
                <>
                  This endpoint does not publish capabilities, so image support
                  is unconfirmed. It must implement{" /images/generations "}or
                  {" /images"}. Testing runs real inference and may cost money.
                </>
              ) : (
                <>
                  This endpoint does not publish capabilities, so chat support
                  is unconfirmed. Testing sends one short prompt and may cost
                  money.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={`Test generated by ${trying?.model.name}`}
              className="max-h-64 w-full rounded-md object-contain"
            />
          ) : null}
          {reply ? (
            <p className="max-h-48 overflow-y-auto rounded-md border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
              {reply}
            </p>
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setTrying(null)}>
              Cancel
            </Button>
            <Button
              variant="outline"
              disabled={testBusy || !trying}
              onClick={runTest}
            >
              {testBusy ? <Spinner data-icon="inline-start" /> : null}
              {trying?.role === "image_generation" ? "Test image" : "Test chat"}
            </Button>
            <Button
              disabled={!trying}
              onClick={() =>
                trying &&
                void assign(trying.role, trying.model, trying.unlisted ?? false)
              }
            >
              {previewUrl || reply ? "Use this model" : "Use without testing"}
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
