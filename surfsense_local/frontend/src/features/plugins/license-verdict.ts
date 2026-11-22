import type { QueryClient } from "@tanstack/react-query"

import { requestVoid } from "@/lib/api"

import { pluginsQueryKey } from "./api"

/**
 * Asks the plugin host whether the license unlocks the paid plugins, then shows its
 * answer. `ifStale` asks only when the last answer is over five minutes old.
 */
export async function refreshLicenseVerdict(
  queryClient: QueryClient,
  { ifStale }: { ifStale: boolean }
): Promise<void> {
  try {
    await requestVoid(
      `/plugins/license/check${ifStale ? "?if_stale=true" : ""}`,
      { method: "POST" }
    )
  } catch {
    // No answer is no news: the plugins keep the verdict they had.
    return
  }
  await queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
}
