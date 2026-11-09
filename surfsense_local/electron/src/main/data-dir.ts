import { join, posix } from "node:path"

import { isOwnSnap } from "./install-channel/own-snap.ts"

type Env = Record<string, string | undefined>

export type DataDirs = {
  /** Models, workspaces and settings: everything that must outlive the app's files. */
  data: string
  /** A TMPDIR for the app and its sidecars in place of the system's; null keeps the system's. */
  temp: string | null
}

/**
 * Where this run keeps its data. A snap's HOME is SNAP_USER_DATA, which snapd
 * copies on every refresh, and its default TMPDIR is a small tmpfs, so a snap
 * keeps both in SNAP_USER_COMMON instead.
 */
export function dataDirs(options: {
  packaged: boolean
  env: Env
  home: string
  execPath: string
}): DataDirs {
  const { packaged, env, home, execPath } = options
  const common = env.SNAP_USER_COMMON
  if (packaged && common && isOwnSnap(env, execPath)) {
    return { data: posix.join(common, ".surfsense"), temp: posix.join(common, "tmp") }
  }
  // Dev keeps its own dir so testing never leaks into the real install's ~/.surfsense.
  return { data: join(home, packaged ? ".surfsense" : ".surfsense-dev"), temp: null }
}
