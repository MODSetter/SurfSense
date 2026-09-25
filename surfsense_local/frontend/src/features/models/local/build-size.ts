import type { LocalBuild } from "./chat/api"

/**
 * The size a build's row states: what Download fetches until the build is on
 * disk, which a file another model already brought makes smaller, and then
 * what it takes there.
 */
export function buildSize(build: LocalBuild): number {
  if (build.installed_as) return build.footprint_bytes
  return build.download_bytes ?? build.footprint_bytes
}
