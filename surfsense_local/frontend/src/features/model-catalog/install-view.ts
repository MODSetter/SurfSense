import type { InstallEvent } from "./api"

const bytes = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  }).format(value / 1e9)

export type InstallView = {
  /** One word, for somewhere with no room. */
  short: string
  label: string
  detail: string | null
  /** Null where nothing has a figure to report, which is not the same as zero. */
  percent: number | null
}

/**
 * What one install event looks like on screen.
 *
 * Its own file because the button and the progress bar both read it, and a
 * button still saying "Download" while the bar below it fills is the state
 * that reads as broken.
 */
export function installView(event: InstallEvent): InstallView {
  if (event.type === "downloading") {
    return {
      short: "Downloading",
      label: event.message || "Downloading",
      detail:
        event.total > 0
          ? `${bytes(event.completed)} of ${bytes(event.total)}`
          : null,
      percent:
        event.total > 0
          ? Math.min(100, Math.round((event.completed / event.total) * 100))
          : null,
    }
  }

  if (event.type === "preparing") {
    // The runtime reports its own load progress, so this wait moves for the
    // same reason the download did instead of sitting still for half a minute.
    return {
      short: "Preparing",
      label: event.message || "Preparing",
      detail: null,
      percent:
        typeof event.progress === "number"
          ? Math.min(100, Math.round(event.progress * 100))
          : null,
    }
  }

  const message = "message" in event ? event.message : undefined
  const rest: Record<string, string> = {
    starting: "Starting",
    verifying: "Verifying",
    selecting: "Selecting",
    complete: "Done",
  }
  return {
    short: rest[event.type] ?? "Failed",
    label: message || rest[event.type] || "Install failed",
    detail: null,
    percent: event.type === "complete" ? 100 : null,
  }
}
