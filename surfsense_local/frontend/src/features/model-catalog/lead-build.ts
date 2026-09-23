import type { LocalBuild, LocalRow } from "./api"

/**
 * The build a row leads with: what is on disk, else what the server recommends
 * for this machine, else the model's default. Chosen here only among answers
 * the server already gave; nothing is priced or ranked in the renderer.
 */
export function leadBuild(row: LocalRow): LocalBuild | undefined {
  return (
    row.builds.find((b) => b.selected) ??
    row.builds.find((b) => b.installed_as) ??
    row.builds.find((b) => b.recommended) ??
    row.builds.find((b) => b.quantization === row.default_quantization) ??
    row.builds[0]
  )
}
