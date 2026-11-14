import type { ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { vi } from "vitest"

import { AppDialogs } from "@/components/ui/app-dialog-slot"
import { EgressPrompt } from "@/features/egress/egress-prompt"
import { listArtifacts } from "@/features/studio/api"
import { OpenArtifactContext } from "@/features/studio/open-artifact"
import { studioKeys } from "@/features/studio/query-keys"
import { render } from "@/test-utils"

import { JobsDialog, type JobsDialogProps } from "./jobs-dialog"
import { LOCAL_SELECTION } from "./stub-jobs-api"

/**
 * Jobs open over workspace 1 as the dashboard mounts it: inside Studio's
 * opener, beside Studio's list, with the consent question when `consent` is set.
 */
export function renderJobsDialog(
  overrides: Partial<JobsDialogProps> = {},
  { consent = false, beside }: { consent?: boolean; beside?: ReactNode } = {}
) {
  // Studio's list as the dashboard keeps it mounted, so a test sees it read again.
  function StudioListReader({ workspaceId }: { workspaceId: number }) {
    useQuery({
      queryKey: studioKeys.artifacts(workspaceId),
      queryFn: ({ signal }) => listArtifacts(workspaceId, signal),
    })
    return null
  }
  const openArtifact = vi.fn<(artifactId: number) => void>()
  const props: JobsDialogProps = {
    open: true,
    onOpenChange: vi.fn(),
    workspaceId: 1,
    documents: [],
    includedDocumentIds: [],
    selection: LOCAL_SELECTION,
    providerAvailable: true,
    onUploadSources: vi.fn(),
    onOpenModelSettings: vi.fn(),
    onOpenLicense: vi.fn(),
    ...overrides,
  }
  const tree = (
    <OpenArtifactContext.Provider value={openArtifact}>
      <JobsDialog {...props} />
      <StudioListReader workspaceId={props.workspaceId} />
      {beside}
    </OpenArtifactContext.Provider>
  )
  const rendered = render(
    consent ? <AppDialogs dialogs={[EgressPrompt]}>{tree}</AppDialogs> : tree
  )
  return { ...rendered, props, openArtifact }
}
