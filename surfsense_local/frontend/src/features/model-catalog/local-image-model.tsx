import { useEffect, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { setSelection } from "@/features/model-selection/api"

import {
  deleteLocalImageModel,
  getLocalImageCatalog,
  installLocalImageModel,
  type DownloadStep,
  type LocalImageCatalog,
  type LocalImageModel as ImageModel,
} from "./api"

const gigabytes = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  }).format(value / 1e9)

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "The request failed"
}

/**
 * Image generation on this machine. Hidden entirely where no sd-server shipped
 * for the platform, so the absence needs no explaining.
 */
export function LocalImageModel({ disabled = false }: { disabled?: boolean }) {
  const [catalog, setCatalog] = useState<LocalImageCatalog | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [step, setStep] = useState<DownloadStep | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const request = useRef<AbortController | null>(null)

  const refresh = (signal?: AbortSignal) =>
    getLocalImageCatalog(signal).then(setCatalog)

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(messageFrom(cause))
    })
    return () => {
      controller.abort()
      request.current?.abort()
    }
  }, [])

  // sd-server only starts once a model is chosen and its weights are on disk,
  // so a fresh pick is selected-but-not-ready for a few seconds.
  const selected = catalog?.models?.some((model) => model.selected) ?? false
  useEffect(() => {
    if (!selected || catalog?.ready) return
    const timer = window.setInterval(() => void refresh().catch(() => {}), 3000)
    return () => window.clearInterval(timer)
  }, [selected, catalog?.ready])

  // Say nothing rather than break the page: this sits inside the local catalogue,
  // and a build with no sd-server is the normal case on some platforms.
  if (!catalog?.offered || !catalog.models?.length) return null

  const install = (model: ImageModel) => {
    const controller = new AbortController()
    request.current = controller
    setDownloading(model.name)
    setError(null)
    setStep({ status: "starting", completed: 0, total: model.size_bytes })
    void installLocalImageModel(model.name, setStep, controller.signal)
      .then(() => refresh())
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
      .finally(() => {
        setDownloading(null)
        setStep(null)
        request.current = null
      })
  }

  const discard = (model: ImageModel) => {
    setBusy(model.name)
    setError(null)
    void deleteLocalImageModel(model.name)
      .then(() => refresh())
      .catch((cause: unknown) => setError(messageFrom(cause)))
      .finally(() => setBusy(null))
  }

  const use = (model: ImageModel) => {
    setBusy(model.name)
    setError(null)
    void setSelection("image_gen", {
      provider: catalog.provider,
      connection_id: null,
      name: model.name,
    })
      .then(() => refresh())
      .catch((cause: unknown) => setError(messageFrom(cause)))
      .finally(() => setBusy(null))
  }

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h3 className="text-sm font-medium">Image models</h3>
        <p className="text-xs text-muted-foreground">
          Generate images on this computer. Downloaded only when you pick one.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {catalog.models.map((model) => {
          const active = downloading === model.name
          const percent =
            active && step && step.total > 0
              ? Math.min(100, Math.round((step.completed / step.total) * 100))
              : null

          return (
            <div
              key={model.name}
              className="flex flex-col gap-2 rounded-lg border p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-medium">
                    {model.label}
                    {model.selected ? (
                      <Badge variant="secondary">
                        {catalog.ready ? "In use" : "Starting…"}
                      </Badge>
                    ) : null}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {model.detail}{" "}
                    {model.installed
                      ? null
                      : `${gigabytes(model.size_bytes)} download.`}
                  </p>
                </div>
                {model.installed ? (
                  <div className="flex shrink-0 gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={disabled || busy !== null || model.selected}
                      onClick={() => discard(model)}
                    >
                      Remove
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={disabled || busy !== null || model.selected}
                      onClick={() => use(model)}
                    >
                      {busy === model.name ? (
                        <Spinner data-icon="inline-start" />
                      ) : null}
                      {model.selected ? "In use" : "Use for images"}
                    </Button>
                  </div>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    disabled={disabled || downloading !== null}
                    onClick={() => install(model)}
                  >
                    {active ? <Spinner data-icon="inline-start" /> : null}
                    Download
                  </Button>
                )}
              </div>

              {active ? (
                <div
                  className="h-1.5 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-label={`Downloading ${model.label}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent ?? undefined}
                >
                  <div
                    className="h-full rounded-full bg-primary transition-[width]"
                    style={{ width: `${percent ?? 8}%` }}
                  />
                </div>
              ) : null}
            </div>
          )
        })}
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}
