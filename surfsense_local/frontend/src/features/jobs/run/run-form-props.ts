import type { ModelSelection } from "@/features/models/selection/api"
import type { WorkspaceDocument } from "@/features/sources/api"

/** What every run form is given: the job, the workspace's sources, and the
 *  chat model the app has selected, which the worker resolves again when the
 *  run begins. */
export type RunFormProps = {
  workspaceId: number
  // The installed job's key, which the run sends.
  job: string
  title: string
  documents: readonly WorkspaceDocument[]
  includedDocumentIds: readonly number[]
  selection: ModelSelection | null
  providerAvailable: boolean
  onUploadSources: (files: File[]) => unknown
  onChooseModel: () => void
  onStarted: (runId: number) => void
  onBack: () => void
}
