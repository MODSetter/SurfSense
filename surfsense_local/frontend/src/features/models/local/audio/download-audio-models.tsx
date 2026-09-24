import { CircleAlertIcon, DownloadIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

import { AudioDownloadProgress } from "./audio-download-progress"
import { describeAudioModel } from "./describe-audio-model"
import { useAudioInstall } from "./use-audio-install"
import { useLocalAudioCatalog } from "./use-local-audio-catalog"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "The request failed"
}

/** Audio models audio.cpp can run on this computer. */
export function DownloadAudioModels() {
  const catalog = useLocalAudioCatalog()
  const { installState, install, cancelInstall } = useAudioInstall()

  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Could not load local audio models</AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  const models = catalog.data.models
  if (models.length === 0) {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>Audio models cannot run on this computer</AlertTitle>
        <AlertDescription>
          This build has no local audio runtime. Use a server above instead.
        </AlertDescription>
      </Alert>
    )
  }

  const installing = installState.status === "installing"

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y overflow-hidden rounded-xl border bg-card">
        {models.map((model) => {
          const active = installing && installState.id === model.id
          return (
            <li key={model.id} className="flex flex-col gap-2 px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{model.label}</p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {describeAudioModel(model)}
                  </p>
                </div>
                {model.installed_as !== null ? (
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
                <AudioDownloadProgress
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
