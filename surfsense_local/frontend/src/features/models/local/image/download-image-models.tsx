import { CircleAlertIcon, DownloadIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

import { ImageDownloadProgress } from "./image-download-progress"
import { useImageInstall } from "./use-image-install"
import { useLocalImageCatalog } from "./use-local-image-catalog"

const gigabytes = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  }).format(value / 1e9)

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "The request failed"
}

/** Image models sd-server can run on this computer. */
export function DownloadImageModels() {
  const catalog = useLocalImageCatalog()
  const { installState, install, cancelInstall } = useImageInstall()

  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Could not load local image models</AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  const models = catalog.data.offered ? (catalog.data.models ?? []) : []
  if (models.length === 0) {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>Image models cannot run on this computer</AlertTitle>
        <AlertDescription>
          This build has no local image runtime. Use a server above instead.
        </AlertDescription>
      </Alert>
    )
  }

  const installing = installState.status === "installing"

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y overflow-hidden rounded-xl border bg-card">
        {models.map((model) => {
          const active = installing && installState.name === model.name
          return (
            <li key={model.name} className="flex flex-col gap-2 px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{model.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {model.detail}{" "}
                    <span className="tabular-nums">
                      {gigabytes(model.size_bytes)}
                    </span>
                  </p>
                </div>
                {model.installed ? (
                  <Button type="button" size="sm" variant="outline" disabled>
                    Downloaded
                  </Button>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    disabled={installing}
                    aria-label={`Download ${model.label}`}
                    onClick={() => void install(model)}
                  >
                    {active ? (
                      <Spinner data-icon="inline-start" />
                    ) : (
                      <DownloadIcon data-icon="inline-start" />
                    )}
                    Download
                  </Button>
                )}
              </div>
              {active ? (
                <ImageDownloadProgress
                  label={model.label}
                  step={installState.step}
                  onCancel={cancelInstall}
                />
              ) : null}
            </li>
          )
        })}
      </ul>
      {installState.status === "idle" && installState.error ? (
        <p className="text-sm text-destructive" role="alert">
          {installState.error}
        </p>
      ) : null}
    </div>
  )
}
