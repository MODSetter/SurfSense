import { statSync } from "node:fs"

/** Size and mtime, which is enough to notice a rewrite and costs no read. */
export function fileStamp(path: string): string {
  try {
    const stats = statSync(path)
    return `${stats.size}:${stats.mtimeMs}`
  } catch {
    return "absent"
  }
}