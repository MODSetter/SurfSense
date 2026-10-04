import { intl } from "@/i18n/intl"

import type { Load, Meter, ResourceUsage } from "./api"
import { formatMemory, formatPercent, GIB, isGigabytes } from "./format-usage"

/** One meter: a bar split into the app's share and everyone else's, then free. */
export type UsageRow = {
  key: string
  label: string
  max: number
  now: number
  // Percent of the bar's length.
  appShare: number
  otherShare: number
  // The whole reading as a sentence; the bar's accessible value.
  valueText: string
  machine: string
  // Null where the system cannot say what the app's share is.
  app: string | null
  // Nearly full, where a model load starts spilling or paging.
  nearlyFull: boolean
}

// RAM and VRAM at 90% leave too little for the next model's working set.
const NEARLY_FULL = 0.9
const MIB = 1024 ** 2

export function usageRows(usage: ResourceUsage): UsageRow[] {
  const numbered = usage.gpus.length > 1
  return [
    loadRow(
      "cpu",
      intl.formatMessage({
        id: "resources_cpu_label",
        defaultMessage: "CPU",
      }),
      usage.cpu
    ),
    memoryRow(
      "ram",
      intl.formatMessage({
        id: "resources_ram_label",
        defaultMessage: "RAM",
      }),
      usage.memory
    ),
    ...usage.gpus.flatMap((gpu, index) => {
      const gpuRow = loadRow(
        `gpu-${index}`,
        gpuLabel(numbered, index),
        gpu.load
      )
      // Unified memory is system RAM, already on the RAM row.
      if (gpu.unified_memory) return [gpuRow]
      return [
        memoryRow(`vram-${index}`, vramLabel(numbered, index), gpu.memory),
        gpuRow,
      ]
    }),
  ]
}

function memoryRow(key: string, label: string, meter: Meter): UsageRow {
  const total = Math.max(meter.total_bytes, 1)
  const used = clamp(meter.used_bytes, 0, total)
  const app = meter.app_bytes === null ? null : clamp(meter.app_bytes, 0, used)
  return {
    key,
    label,
    max: total,
    now: used,
    appShare: ((app ?? 0) / total) * 100,
    otherShare: ((used - (app ?? 0)) / total) * 100,
    valueText: memoryValueText(used, total, app),
    machine: intl.formatMessage(
      {
        id: "resources_memory_used_label",
        defaultMessage:
          "{used, number, ::.0} / {total, number, ::unit/gigabyte .0}",
      },
      { used: used / GIB, total: total / GIB }
    ),
    app: app === null ? null : formatMemory(app),
    nearlyFull: used / total >= NEARLY_FULL,
  }
}

function loadRow(key: string, label: string, load: Load): UsageRow {
  const percent = load.percent === null ? null : clamp(load.percent, 0, 100)
  // Sampled a moment apart, the app can read a hair over the machine.
  const app =
    load.app_percent === null
      ? null
      : clamp(load.app_percent, 0, percent ?? 100)
  return {
    key,
    label,
    max: 100,
    now: percent ?? 0,
    appShare: app ?? 0,
    otherShare: (percent ?? 0) - (app ?? 0),
    valueText: loadValueText(percent, app),
    machine: percent === null ? "—" : formatPercent(percent),
    app: app === null ? null : formatPercent(app),
    nearlyFull: false,
  }
}

function memoryValueText(
  used: number,
  total: number,
  app: number | null
): string {
  if (app === null) {
    return intl.formatMessage(
      {
        id: "resources_memory_unattributed_aria",
        defaultMessage:
          "{used, number, ::unit/gigabyte .0} of {total, number, ::unit/gigabyte .0} in use. SurfSense’s share isn’t reported on this system.",
      },
      { used: used / GIB, total: total / GIB }
    )
  }
  if (isGigabytes(app)) {
    return intl.formatMessage(
      {
        id: "resources_memory_gigabytes_aria",
        defaultMessage:
          "{used, number, ::unit/gigabyte .0} of {total, number, ::unit/gigabyte .0} in use. SurfSense is using {app, number, ::unit/gigabyte .0}.",
      },
      { used: used / GIB, total: total / GIB, app: app / GIB }
    )
  }
  return intl.formatMessage(
    {
      id: "resources_memory_megabytes_aria",
      defaultMessage:
        "{used, number, ::unit/gigabyte .0} of {total, number, ::unit/gigabyte .0} in use. SurfSense is using {app, number, ::unit/megabyte}.",
    },
    { used: used / GIB, total: total / GIB, app: Math.round(app / MIB) }
  )
}

function loadValueText(percent: number | null, app: number | null): string {
  if (percent === null) {
    return intl.formatMessage({
      id: "resources_load_unknown_aria",
      defaultMessage: "Not reported on this system.",
    })
  }
  if (app === null) {
    return intl.formatMessage(
      {
        id: "resources_load_unattributed_aria",
        defaultMessage:
          "{percent, number, ::percent} busy. SurfSense’s share isn’t reported on this system.",
      },
      { percent: percent / 100 }
    )
  }
  return intl.formatMessage(
    {
      id: "resources_load_aria",
      defaultMessage:
        "{percent, number, ::percent} busy. SurfSense is using {app, number, ::percent}.",
    },
    { percent: percent / 100, app: app / 100 }
  )
}

export function gpuLabel(numbered: boolean, index: number): string {
  return numbered
    ? intl.formatMessage(
        {
          id: "resources_gpu_numbered_label",
          defaultMessage: "GPU {index, number}",
        },
        { index: index + 1 }
      )
    : intl.formatMessage({
        id: "resources_gpu_label",
        defaultMessage: "GPU",
      })
}

function vramLabel(numbered: boolean, index: number): string {
  return numbered
    ? intl.formatMessage(
        {
          id: "resources_vram_numbered_label",
          defaultMessage: "VRAM {index, number}",
        },
        { index: index + 1 }
      )
    : intl.formatMessage({
        id: "resources_vram_label",
        defaultMessage: "VRAM",
      })
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}
