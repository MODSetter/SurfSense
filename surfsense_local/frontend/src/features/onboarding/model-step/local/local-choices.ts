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
 * Every model this computer can run, in the order onboarding lists them: what
 * the user fetched from Hugging Face first, since they went looking for it,
 * then the curated list as the server orders it, starred model first. A
 * searched model appears only once it is on disk.
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
  const curated = runnable.filter((row) => row.origin === "curated")
  return [
    ...runnable.filter((row) => row.origin !== "curated"),
    ...curated.filter((row) => row.recommended),
    ...curated.filter((row) => !row.recommended),
  ]
}
