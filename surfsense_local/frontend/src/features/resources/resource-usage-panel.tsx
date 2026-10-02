import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { intl } from "@/i18n/intl"

import type { ResourceUsage } from "./api"
import { EngineBreakdown } from "./engine-breakdown"
import { GraphicsCards } from "./graphics-cards"
import { UsageMeter } from "./usage-meter"
import { usageRows } from "./usage-rows"
import { UsageSection } from "./usage-section"

/**
 * The machine's CPU, RAM and graphics card, with the app's share of each in
 * the brand color, so a slow answer can be told apart from a full machine.
 */
export function ResourceUsagePanel({
  usage,
  isError,
}: {
  usage: ResourceUsage | undefined
  isError: boolean
}) {
  return (
    <div className="flex flex-col gap-8 text-sm select-none">
      <UsageSection
        title={intl.formatMessage({
          id: "resources_machine_title",
          defaultMessage: "This computer",
        })}
        body={intl.formatMessage({
          id: "resources_machine_body",
          defaultMessage: "CPU, memory and graphics, all apps together.",
        })}
        aside={<Legend />}
      >
        <MachineMeters usage={usage} isError={isError} />
      </UsageSection>
      {usage ? (
        <>
          <Separator />
          <UsageSection
            title={intl.formatMessage({
              id: "resources_breakdown_title",
              defaultMessage: "By engine",
            })}
            body={intl.formatMessage({
              id: "resources_breakdown_body",
              defaultMessage: "What each part of SurfSense is using right now.",
            })}
          >
            <EngineBreakdown usage={usage} />
          </UsageSection>
        </>
      ) : null}
      {usage && usage.gpus.length > 0 ? (
        <>
          <Separator />
          <UsageSection
            title={intl.formatMessage({
              id: "resources_graphics_title",
              defaultMessage: "Graphics",
            })}
            body={intl.formatMessage({
              id: "resources_graphics_body",
              defaultMessage: "The cards the GPU rows above measure.",
            })}
          >
            <GraphicsCards gpus={usage.gpus} />
          </UsageSection>
        </>
      ) : null}
    </div>
  )
}

function MachineMeters({
  usage,
  isError,
}: {
  usage: ResourceUsage | undefined
  isError: boolean
}) {
  if (usage) {
    return (
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto_auto] items-center gap-x-4 gap-y-3">
        {usageRows(usage).map((row) => (
          <UsageMeter key={row.key} row={row} />
        ))}
      </div>
    )
  }
  return isError ? (
    <p className="text-muted-foreground">
      {intl.formatMessage({
        id: "resources_panel_error",
        defaultMessage: "Usage unavailable",
      })}
    </p>
  ) : (
    <div className="flex flex-col gap-4 py-1">
      <Skeleton className="h-2 w-full" />
      <Skeleton className="h-2 w-full" />
    </div>
  )
}

function Legend() {
  return (
    <div className="flex shrink-0 items-center gap-4 text-muted-foreground">
      <span className="flex items-center gap-2">
        <span aria-hidden className="size-2 rounded-full bg-chart-1" />
        SurfSense
      </span>
      <span className="flex items-center gap-2">
        <span aria-hidden className="size-2 rounded-full bg-chart-3" />
        {intl.formatMessage({
          id: "resources_legend_other_label",
          defaultMessage: "Other apps",
        })}
      </span>
    </div>
  )
}
