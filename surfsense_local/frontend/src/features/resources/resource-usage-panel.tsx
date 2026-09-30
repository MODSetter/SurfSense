import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { ChevronDownIcon } from "@/components/ui/icons"
import { Skeleton } from "@/components/ui/skeleton"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { ResourceUsage } from "./api"
import { readBreakdownOpen, writeBreakdownOpen } from "./breakdown-pref"
import { EngineBreakdown } from "./engine-breakdown"
import { UsageMeter } from "./usage-meter"
import { usageRows } from "./usage-rows"

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
  const titleId = useId()
  const breakdownId = useId()
  const [open, setOpen] = useState(readBreakdownOpen)
  const toggle = () => {
    setOpen(!open)
    writeBreakdownOpen(!open)
  }

  return (
    <section
      aria-labelledby={titleId}
      className="rounded-xl border bg-card px-3 py-2.5 text-xs select-none"
    >
      <header className="flex items-center gap-3">
        <h3 id={titleId} className="font-medium text-foreground">
          {intl.formatMessage({
            id: "resources_panel_title",
            defaultMessage: "Resources",
          })}
        </h3>
        <Legend />
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="-mr-1"
          aria-expanded={open}
          aria-controls={open ? breakdownId : undefined}
          aria-label={
            open
              ? intl.formatMessage({
                  id: "resources_breakdown_hide_aria",
                  defaultMessage: "Hide usage by engine",
                })
              : intl.formatMessage({
                  id: "resources_breakdown_show_aria",
                  defaultMessage: "Show usage by engine",
                })
          }
          onClick={toggle}
        >
          <ChevronDownIcon
            className={cn(
              "transition-transform duration-200 ease-out motion-reduce:transition-none",
              open && "rotate-180"
            )}
          />
        </Button>
      </header>
      {usage ? (
        <>
          <div className="mt-2 grid grid-cols-[auto_minmax(0,1fr)_auto_auto] items-center gap-x-2.5 gap-y-1.5">
            {usageRows(usage).map((row) => (
              <UsageMeter key={row.key} row={row} />
            ))}
          </div>
          {open ? <EngineBreakdown id={breakdownId} usage={usage} /> : null}
        </>
      ) : isError ? (
        <p className="mt-2 text-secondary-foreground">
          {intl.formatMessage({
            id: "resources_panel_error",
            defaultMessage: "Usage unavailable",
          })}
        </p>
      ) : (
        <div className="mt-2 flex flex-col gap-2.5 py-0.5">
          <Skeleton className="h-2 w-full" />
          <Skeleton className="h-2 w-full" />
        </div>
      )}
    </section>
  )
}

function Legend() {
  return (
    <div className="ml-auto flex items-center gap-3 text-secondary-foreground">
      <span className="flex items-center gap-1.5">
        <span aria-hidden className="size-1.5 rounded-full bg-chart-1" />
        SurfSense
      </span>
      <span className="flex items-center gap-1.5">
        <span aria-hidden className="size-1.5 rounded-full bg-chart-3" />
        {intl.formatMessage({
          id: "resources_legend_other_label",
          defaultMessage: "Other apps",
        })}
      </span>
    </div>
  )
}
