// Mirrors electron/src/main/storage/. The page names a kind and never a path:
// main opens the picker and holds the plan.
export type StorageKind = "data" | "models"

export type StorageFolder = {
  path: string
  isDefault: boolean
  connected: boolean
  freeBytes: number | null
}

export type StorageState = { data: StorageFolder; models: StorageFolder }

export type StorageRefusalCode =
  | "same_folder"
  | "inside_current"
  | "inside_app"
  | "network_drive"
  | "not_writable"
  | "no_large_files"
  | "no_hard_links"
  | "not_enough_room"
  | "target_occupied"

export type MoveReady = {
  status: "ready"
  kind: StorageKind
  target: string
  neededBytes: number
  freeBytes: number
  adopt: boolean
}

export type PlanResult =
  | MoveReady
  | { status: "canceled" }
  | {
      status: "refused"
      code: StorageRefusalCode
      neededBytes?: number
      freeBytes?: number
    }

export type MoveFailureReason = "no_room" | "verify_failed" | "failed"

export type MoveProgress =
  | { phase: "stopping" }
  | {
      phase: "copying" | "verifying" | "switching"
      doneBytes: number
      totalBytes: number
    }
  | { phase: "failed"; reason: MoveFailureReason }

export type StorageBridge = {
  state: () => Promise<StorageState | null>
  choose: (kind: StorageKind) => Promise<PlanResult>
  planDefault: (kind: StorageKind) => Promise<PlanResult>
  start: () => Promise<boolean>
  cancel: () => Promise<void>
  restart: () => Promise<void>
  onProgress: (listener: (progress: MoveProgress) => void) => () => void
}
