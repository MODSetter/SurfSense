import { Fragment } from "react"

import { DotIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { Budget, GpuStatus } from "./api"
import { describeHardware } from "./describe-hardware"

/** What this machine has, in one line. No scan: the runtime answers in ~180ms. */
export function HardwareSummary({
  budget,
  gpuStatus,
}: {
  budget: Budget | undefined
  gpuStatus: GpuStatus | undefined
}) {
  const parts = budget
    ? describeHardware(budget, gpuStatus ?? "unknown")
    : [intl.formatMessage({ id: "models_hardware_checking_status" })]
  return (
    <div className="rounded-lg bg-muted/50 p-3">
      <p className="flex items-center text-sm font-medium">
        {parts.map((part, index) => (
          <Fragment key={part}>
            {index > 0 ? (
              <DotIcon
                aria-hidden="true"
                className="size-3 shrink-0 text-muted-foreground"
              />
            ) : null}
            <span>{part}</span>
          </Fragment>
        ))}
      </p>
      <p className="text-xs text-muted-foreground">
        {intl.formatMessage({ id: "models_hardware_summary_body" })}
      </p>
    </div>
  )
}
