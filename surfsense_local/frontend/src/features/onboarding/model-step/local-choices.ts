import type { LocalBuild, LocalRow } from "@/features/models/local/chat/api"

/** The build a row shows and downloads, as the server chose it. */
export function leadBuild(row: LocalRow): LocalBuild | null {
  return (
    row.builds.find((build) => build.quantization === row.lead?.quantization) ??
    row.builds[0] ??
    null
  )
}

/**
 * Every model this computer can run, in the order onboarding lists them: the
 * server's starred model first, then the catalog's own order. A searched model
 * appears only once it is on disk, since onboarding has no search.
 */
export function localChoices(rows: LocalRow[]): LocalRow[] {
  const runnable = rows.filter((row) => {
    const build = leadBuild(row)
    return (
      row.runnable &&
      build !== null &&
      (row.origin === "curated" || build.installed_as !== null)
    )
  })
  return [
    ...runnable.filter((row) => row.recommended),
    ...runnable.filter((row) => !row.recommended),
  ]
}
