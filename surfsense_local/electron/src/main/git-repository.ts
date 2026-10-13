/**
 * A git repository above SurfSense's data folder: the hole in the thread
 * folders (docs/architecture/agent.md, Known gaps). opencode looks for `.git`
 * from a thread's folder upward with no ceiling, so a repository that holds the
 * data folder — a home folder kept in git, for one — becomes the project, and
 * every thread's agent can read every other thread's and workspace's folder.
 * Nothing in opencode's flags closes this, so the app says it instead.
 */
import { existsSync } from "node:fs"
import { dirname, join, parse } from "node:path"

/**
 * The folder of the nearest `.git` at or above `folder`, or null when none
 * stands above it. A `.git` file counts too: it is how a worktree and a
 * submodule point at their repository. `stop` bounds the search, mirroring
 * opencode's own `fs.up({ targets, start, stop })`: the walk never reaches it,
 * so tests can keep the machine's own repositories out of the picture.
 */
export function gitRootAbove(folder: string, stop?: string): string | null {
  let current = folder
  while (true) {
    if (stop !== undefined && current === stop) return null
    if (existsSync(join(current, ".git"))) return current
    const parent = dirname(current)
    if (parent === current) return null
    current = parent
  }
}

/** Whether a found root actually holds the data folder, not one beside it. */
export function holds(root: string, folder: string): boolean {
  const home = parse(root).root
  let current = folder
  while (true) {
    if (current === root) return true
    const parent = dirname(current)
    if (parent === current || parent === home) return false
    current = parent
  }
}

/**
 * The `.git` folder above the data folder, or null when the agent is safe to
 * start: either no repository stands above the data folder, or one does but
 * the data folder sits outside it (a sibling folder, or a Windows drive root).
 * Checked once per boot, before the agent can run at all.
 */
export function gitAboveDataFolder(dataDir: string, stop?: string): string | null {
  const root = gitRootAbove(dataDir, stop)
  if (root === null) return null
  return holds(root, dataDir) ? root : null
}
