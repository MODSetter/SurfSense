import { CircleAlertIcon, DownloadIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

import { InstallProgress } from "../chat/install-progress"
import { installView } from "../chat/install-view"
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
          const active =
            installState.status === "installing" &&
            installState.catalogId === model.catalog_id
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
                    onClick={() => void install(model.catalog_id, model.label)}
                  >
                    {/* Names the phase, as chat and image do, so a disabled
                        button over a filling bar reads as busy. */}
                    {active ? (
                      <>
                        <span className="animate-spin" data-icon="inline-start">
                          <Spinner className="size-3.5" />
                        </span>
                        {installView(installState.event).short}
                      </>
                    ) : (
                      <>
                        <DownloadIcon data-icon="inline-start" />
                        Download
                      </>
                    )}
                  </Button>
                )}
              </div>
              {active ? (
                <InstallProgress
                  event={installState.event}
                  onCancel={cancelInstall}
                />
              ) : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
