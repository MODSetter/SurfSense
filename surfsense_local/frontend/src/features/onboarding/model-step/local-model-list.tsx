import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DotIcon, Trash2Icon } from "@/components/ui/icons"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import type { LocalRow } from "@/features/models/local/chat/api"
import { BuildAction } from "@/features/models/local/chat/build-action"
import { FitBadge } from "@/features/models/local/chat/fit-badge"
import { InstallProgress } from "@/features/models/local/chat/install-progress"
import type { InstallState } from "@/features/models/local/create-install"
import { intl } from "@/i18n/intl"

import { leadBuild } from "./local-choices"

const formatSize = (bytes: number) =>
  intl.formatNumber(bytes / 1e9, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  })

/**
 * Every model this computer can run, one line each, the recommended one first.
 * Deliberately short of Settings' catalog: no other builds, no search. Its
 * actions are Settings' own, and a download shows under the row it belongs to.
 */
export function LocalModelList({
  rows,
  installState,
  disabled,
  onDownload,
  onUse,
  onCancel,
  onDelete,
}: {
  rows: LocalRow[]
  installState: InstallState
  disabled: boolean
  onDownload: (row: LocalRow) => void
  onUse: (row: LocalRow) => void
  onCancel: () => void
  onDelete: (row: LocalRow) => void
}) {
  return (
    <ScrollShadow
      className="overflow-hidden rounded-xl border bg-card"
      // Four rows and half of the next: the cut row says the list scrolls.
      viewportClassName="max-h-72"
    >
      <ul
        className="divide-y"
        aria-label={intl.formatMessage({ id: "onboarding_model_list_aria" })}
      >
        {rows.map((row) => {
          const build = leadBuild(row)
          if (!build) return null
          const installed = build.installed_as !== null
          const downloading =
            installState.status === "installing" &&
            installState.catalogId === build.catalog_id
          return (
            <li key={row.id} className="flex flex-col gap-2 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-0.5">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-sm font-medium">
                      {row.name}
                    </span>
                    {row.recommended ? (
                      <Badge variant="secondary">
                        {intl.formatMessage({
                          id: "onboarding_model_list_recommended_label",
                        })}
                      </Badge>
                    ) : null}
                    {row.support.reads_images ? (
                      <Badge variant="secondary">
                        {intl.formatMessage({
                          id: "onboarding_model_list_vision_label",
                        })}
                      </Badge>
                    ) : null}
                    <FitBadge fit={build.fit} copy={build.badge} />
                  </div>
                  <p className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span>{build.quantization}</span>
                    <DotIcon aria-hidden="true" className="size-3" />
                    <span className="tabular-nums">
                      {formatSize(build.footprint_bytes)}
                    </span>
                    {installed ? (
                      <>
                        <DotIcon aria-hidden="true" className="size-3" />
                        <span>
                          {intl.formatMessage({
                            id: "onboarding_model_list_installed_label",
                          })}
                        </span>
                      </>
                    ) : null}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <BuildAction
                    build={build}
                    label={row.name}
                    installState={installState}
                    disabled={disabled}
                    runtimeAvailable
                    onAction={() => (installed ? onUse(row) : onDownload(row))}
                  />
                  {installed ? (
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="destructive"
                      disabled={disabled}
                      aria-label={intl.formatMessage(
                        { id: "onboarding_model_list_delete_aria" },
                        {
                          name: row.name,
                        }
                      )}
                      onClick={() => onDelete(row)}
                    >
                      <Trash2Icon />
                    </Button>
                  ) : null}
                </div>
              </div>
              {downloading && installState.status === "installing" ? (
                <InstallProgress
                  event={installState.event}
                  onCancel={onCancel}
                />
              ) : null}
            </li>
          )
        })}
      </ul>
    </ScrollShadow>
  )
}
