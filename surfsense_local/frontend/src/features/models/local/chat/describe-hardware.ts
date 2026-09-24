import { intl } from "@/i18n/intl"

import type { Budget, GpuStatus } from "./api"

const gb = (bytes: number) =>
  `${intl.formatNumber(bytes / 1e9, { maximumFractionDigits: 1 })} GB`

/**
 * The status is read before the budget: a machine whose card the runtime cannot
 * reach is priced against its processor, and calling it a machine with no card
 * would be a wrong sentence about the user's hardware.
 */
export function describeHardware(budget: Budget, gpuStatus: GpuStatus) {
  if (gpuStatus === "broken_install") {
    return [
      intl.formatMessage({ id: "models_hardware_broken_install_label" }),
      intl.formatMessage(
        { id: "models_hardware_memory_label" },
        {
          size: gb(budget.ram_available_bytes),
        }
      ),
    ]
  }
  if (!budget.has_gpu) {
    return [
      intl.formatMessage({ id: "models_hardware_cpu_label" }),
      intl.formatMessage(
        { id: "models_hardware_memory_label" },
        {
          size: gb(budget.ram_available_bytes),
        }
      ),
    ]
  }
  return [
    budget.uma
      ? intl.formatMessage({ id: "models_hardware_apple_gpu_label" })
      : intl.formatMessage({ id: "models_hardware_gpu_label" }),
    intl.formatMessage(
      { id: "models_hardware_memory_label" },
      {
        size: gb(budget.device_total_bytes),
      }
    ),
  ]
}
