import { useId } from "react"

import { CircleAlertIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"

import type { ModelSelection } from "../../selection/api"
import { useSelect } from "../../selection/use-selection"
import type { LocalBuild, LocalRow } from "./api"
import { HardwareSummary } from "./hardware-summary"
import { ModelCard } from "./model-card"
import { ModelFamilyGroup } from "./model-family-group"
import { ModelSearch } from "./model-search"
import { useChatInstall } from "./use-chat-install"
import { useLocalChatCatalog } from "./use-local-chat-catalog"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

function byFamily(rows: LocalRow[]) {
  const result = new Map<string, LocalRow[]>()
  for (const row of rows) {
    const family = row.family || "Other"
    result.set(family, [...(result.get(family) ?? []), row])
  }
  return result
}

/** Chat models to put on this computer: tested ones first, then all of Hugging Face. */
export function DownloadChatModels({
  onSelected,
}: {
  onSelected?: (selection: ModelSelection) => void
}) {
  const headingId = useId()
  const catalog = useLocalChatCatalog()
  const { installState, install, cancelInstall } = useChatInstall(onSelected)
  const select = useSelect("text_gen")

  // No skeleton: the catalog resolves as fast as any page fetch, so a loading
  // state would only ever flash.
  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Could not load local models</AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  // The catalog also carries image and audio rows; only llama.cpp's are chat.
  const curated = catalog.data.rows.filter(
    (row) => row.origin === "curated" && row.engine === "llamacpp"
  )
  const busy = installState.status === "installing" || select.isPending

  // No confirmation for a partial fit: it runs, slower, and llama.cpp places
  // the layers. Only physics blocks, and that is already `can_install`.
  const act = (build: LocalBuild, label: string) => {
    if (busy) return
    if (build.installed_as) {
      void select
        .mutateAsync({
          target: {
            provider: "llamacpp",
            connection_id: null,
            name: build.installed_as,
          },
        })
        .then((selection) => onSelected?.(selection))
        .catch(() => undefined)
    } else {
      void install(build.catalog_id, label)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <HardwareSummary
        budget={catalog.data.budget}
        gpuStatus={catalog.data.gpu_status}
      />

      {curated.length > 0 ? (
        <section className="flex flex-col gap-2.5" aria-labelledby={headingId}>
          <div>
            <h2 id={headingId} className="font-heading text-sm font-medium">
              Tested by SurfSense
            </h2>
            <p className="text-xs text-muted-foreground">
              Models we have run, priced against this computer.
            </p>
          </div>
          {[...byFamily(curated)].map(([family, rows]) => (
            <ModelFamilyGroup key={family} family={family}>
              {rows.map((row) => (
                // The row's id, not an install token: a token may be reissued,
                // and keying on it would remount the row each time.
                <li key={row.id}>
                  <ModelCard
                    row={row}
                    installState={installState}
                    actionsDisabled={busy}
                    runtimeAvailable
                    onAction={(build) =>
                      act(build, `${row.name} ${build.quantization}`)
                    }
                    onCancel={cancelInstall}
                  />
                </li>
              ))}
            </ModelFamilyGroup>
          ))}
        </section>
      ) : (
        <Alert>
          <CircleAlertIcon />
          <AlertTitle>No tested models could be read</AlertTitle>
          <AlertDescription>
            You can still search Hugging Face below.
          </AlertDescription>
        </Alert>
      )}

      <Separator />

      <ModelSearch
        onInstall={act}
        onCancel={cancelInstall}
        installState={installState}
        disabled={busy}
      />

      {select.isError ? (
        <p className="text-sm text-destructive">{messageFrom(select.error)}</p>
      ) : null}
    </div>
  )
}
