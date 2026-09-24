import type { Budget, GpuStatus } from "./api"

const gb = (bytes: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`

/**
 * The status is read before the budget: a machine whose card the runtime cannot
 * reach is priced against its processor, and calling it a machine with no card
 * would be a wrong sentence about the user's hardware.
 */
export function describeHardware(budget: Budget, gpuStatus: GpuStatus) {
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
