import type { AppDetails } from "@/lib/api"

// Stays English in every language: it is pasted into GitHub issues for maintainers.
export function systemInfo(details: AppDetails): string {
  return [
    `SurfSense ${details.version}`,
    `${details.os} (${details.arch})`,
    `Electron ${details.electron} · Chromium ${details.chrome} · Node ${details.node}`,
  ].join("\n")
}
