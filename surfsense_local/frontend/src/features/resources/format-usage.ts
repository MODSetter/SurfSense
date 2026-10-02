import { intl } from "@/i18n/intl"

// Binary units, as Task Manager and Activity Monitor count memory: a 16 GiB
// machine reads 16.0 GB, not the 17.2 a decimal gigabyte would print.
export const GIB = 1024 ** 3
const MIB = 1024 ** 2

/** Megabytes below one gigabyte, so a small process is not "0.0 GB". */
export function isGigabytes(bytes: number): boolean {
  return bytes >= 1000 * MIB
}

export function formatMemory(bytes: number): string {
  return isGigabytes(bytes)
    ? intl.formatNumber(bytes / GIB, {
        style: "unit",
        unit: "gigabyte",
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })
    : intl.formatNumber(bytes / MIB, {
        style: "unit",
        unit: "megabyte",
        maximumFractionDigits: 0,
      })
}

export function formatPercent(percent: number): string {
  return intl.formatNumber(percent / 100, {
    style: "percent",
    maximumFractionDigits: 0,
  })
}
