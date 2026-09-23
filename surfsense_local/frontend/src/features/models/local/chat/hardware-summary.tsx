import { Fragment } from "react"

import { DotIcon } from "@/components/ui/icons"

import type { Budget, GpuStatus } from "./api"

const gb = (bytes: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`

/**
 * The status is read before the budget: a machine whose card the runtime cannot
 * reach is priced against its processor, and calling it a machine with no card
 * would be a wrong sentence about the user's hardware.
 */
function describe(budget: Budget, gpuStatus: GpuStatus) {
  if (gpuStatus === "broken_install") {
    return [
      "Graphics card not detected by the runtime. Reinstall to fix",
      `${gb(budget.ram_available_bytes)} memory`,
    ]
  }
  if (!budget.has_gpu) {
    return [
      "Runs on your processor",
      `${gb(budget.ram_available_bytes)} memory`,
    ]
  }
  return [
    budget.uma ? "Apple Silicon GPU" : "Graphics card",
    `${gb(budget.device_total_bytes)} memory`,
  ]
}

/** What this machine has, in one line. No scan: the runtime answers in ~180ms. */
export function HardwareSummary({
  budget,
  gpuStatus,
}: {
  budget: Budget | undefined
  gpuStatus: GpuStatus | undefined
}) {
  const parts = budget
    ? describe(budget, gpuStatus ?? "unknown")
    : ["Checking this computer"]
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
        Every model below is priced against this computer.
      </p>
    </div>
  )
}
