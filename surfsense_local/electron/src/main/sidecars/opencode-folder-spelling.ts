/**
 * One spelling for every folder opencode is given. 2.x keeps `c:\` and `C:\`,
 * or a trailing `\`, as separate locations, so one thread's sessions would split.
 */
import { resolve, win32 } from "node:path"

import { isWindows } from "./platform.ts"

export function oneSpelling(folder: string): string {
  if (!isWindows) return resolve(folder)
  const resolved = win32.resolve(folder)
  return resolved[0].toUpperCase() + resolved.slice(1)
}
