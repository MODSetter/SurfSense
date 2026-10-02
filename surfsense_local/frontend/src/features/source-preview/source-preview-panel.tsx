import { useState } from "react"

import { Button } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
import type { WorkspaceDocument } from "@/features/sources/api"
import { originalDocumentUrl } from "@/features/sources/api"
import { intl } from "@/i18n/intl"
import { getFileViewer } from "@/features/file-viewers/registry"

export function SourcePreviewPanel({
  workspaceId,
  document,
  onOpen,
  onClose,
}: {
  workspaceId: number
  document: WorkspaceDocument
  onOpen: () => void
  onClose: () => void
}) {
  const [actionsContainer, setActionsContainer] =
    useState<HTMLDivElement | null>(null)
  const Viewer = getFileViewer(document.mime_type)
  const mimeType = document.mime_type
  if (!Viewer || !mimeType) return null

  return (
    <DetailPanel
      title={document.title}
      titleClassName="select-none"
      ariaLabel={intl.formatMessage({
        id: "source_preview_panel_aria",
        defaultMessage: "Source preview",
      })}
      closeLabel={intl.formatMessage({
        id: "source_preview_panel_close_aria",
        defaultMessage: "Close source preview",
      })}
      onClose={onClose}
      flush
      actions={
        <>
          <div ref={setActionsContainer} className="flex items-center gap-1" />
          <Button
            variant="default"
            size="sm"
            className="h-6 px-1.5 text-[11px]"
            onClick={onOpen}
          >
            {intl.formatMessage({
              id: "source_preview_panel_open_file_button",
              defaultMessage: "Open file",
            })}
          </Button>
        </>
      }
    >
      <div className="h-full overflow-hidden">
        <div className="h-full">
          {/* getFileViewer returns a stable registry reference. */}
          {/* eslint-disable-next-line react-hooks/static-components */}
          <Viewer
            url={originalDocumentUrl(workspaceId, document.id)}
            mimeType={mimeType}
            sizeBytes={null}
            title={document.title}
            actionsContainer={actionsContainer}
          />
        </div>
      </div>
    </DetailPanel>
  )
}
