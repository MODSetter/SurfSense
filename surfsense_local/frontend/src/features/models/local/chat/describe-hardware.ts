import { intl } from "@/i18n/intl"

import type { Budget, GpuStatus } from "./api"

/**
 * The status is read before the budget: a machine whose card the runtime cannot
 * reach is priced against its processor, and calling it a machine with no card
 * would be a wrong sentence about the user's hardware.
 */
export function describeHardware(budget: Budget, gpuStatus: GpuStatus) {
  if (gpuStatus === "broken_install") {
    return [
      intl.formatMessage({
        id: "models_hardware_broken_install_label",
        defaultMessage:
          "Graphics card not detected by the runtime. Reinstall to fix",
      }),
      intl.formatMessage(
        {
          id: "models_hardware_memory_label",
          defaultMessage: "{size, number, ::unit/gigabyte .#} memory",
        },
        {
          size: budget.ram_available_bytes / 1e9,
        }
      ),
    ]
  }
  if (!budget.has_gpu) {
    return [
      intl.formatMessage({
        id: "models_hardware_cpu_label",
        defaultMessage: "Runs on your processor",
      }),
      intl.formatMessage(
        {
          id: "models_hardware_memory_label",
          defaultMessage: "{size, number, ::unit/gigabyte .#} memory",
        },
        {
          size: budget.ram_available_bytes / 1e9,
        }
      ),
    ]
  }
  return [
    budget.uma
      ? intl.formatMessage({
          id: "models_hardware_apple_gpu_label",
          defaultMessage: "Apple Silicon GPU",
        })
      : intl.formatMessage({
          id: "models_hardware_gpu_label",
          defaultMessage: "Graphics card",
        }),
    intl.formatMessage(
      {
        id: "models_hardware_memory_label",
        defaultMessage: "{size, number, ::unit/gigabyte .#} memory",
      },
      {
        size: budget.device_total_bytes / 1e9,
      }
    ),
  ]
}
