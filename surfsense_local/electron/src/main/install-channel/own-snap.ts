type Env = Record<string, string | undefined>

/** The store name, from executableName in electron-builder.yml; parallel installs keep it too. */
const SNAP_NAME = "surfsense-local"

/**
 * Whether this run is SurfSense's own snap. Children of a classic snap inherit
 * its SNAP_* variables, so a normal install can see another snap's.
 */
export function isOwnSnap(env: Env, execPath: string): boolean {
  return env.SNAP_NAME === SNAP_NAME && !!env.SNAP && execPath.startsWith(`${env.SNAP}/`)
}
