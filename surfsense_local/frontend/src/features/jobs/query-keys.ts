export const jobsKeys = {
  all: ["jobs"] as const,
  packs: () => [...jobsKeys.all, "packs"] as const,
  settingsAll: () => [...jobsKeys.all, "settings"] as const,
  settings: (job: string) => [...jobsKeys.settingsAll(), job] as const,
  runs: (workspaceId: number) =>
    [...jobsKeys.all, "runs", workspaceId] as const,
  // Under runs, so one invalidation of a workspace's runs re-reads each open one too.
  run: (workspaceId: number, rootId: number) =>
    [...jobsKeys.runs(workspaceId), rootId] as const,
  // Client state, never fetched: each job's last download. Outside `all`, so
  // no jobs invalidation clears it.
  delivery: () => ["job-pack-delivery"] as const,
}
