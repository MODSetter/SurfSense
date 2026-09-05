import { createWorkspace, listWorkspaces, type Workspace } from "./api"

let inFlightBootstrap: Promise<Workspace[]> | null = null

export function bootstrapWorkspaces(): Promise<Workspace[]> {
  if (inFlightBootstrap) {
    return inFlightBootstrap
  }

  // ponytail: one local renderer owns bootstrap; replace this guard with an
  // idempotent backend endpoint before allowing multiple app windows.
  inFlightBootstrap = (async () => {
    const workspaces = await listWorkspaces()
    if (workspaces.length > 0) {
      return workspaces
    }
    return [await createWorkspace("My Workspace")]
  })()

  void inFlightBootstrap.then(
    () => {
      inFlightBootstrap = null
    },
    () => {
      inFlightBootstrap = null
    }
  )
  return inFlightBootstrap
}
