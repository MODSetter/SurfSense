"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { ArtifactFile } from "./model";

export interface ArtifactFileViewerProps {
	primary: ArtifactFile;
	files: ArtifactFile[];
	zoomControlsContainer?: HTMLElement | null;
}

const PdfFileViewer = dynamic<ArtifactFileViewerProps>(() => import("./pdf-file-viewer"), {
	ssr: false,
});
const PdfPreviewViewer = dynamic<ArtifactFileViewerProps>(() => import("./pdf-preview-viewer"), {
	ssr: false,
});

// Unknown MIME types deliberately fall through to the panel's unviewable state,
// where the header's download button is still the way out.
export const VIEWERS: Partial<Record<string, ComponentType<ArtifactFileViewerProps>>> = {
	"application/pdf": PdfFileViewer,
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document": PdfPreviewViewer,
	"application/vnd.openxmlformats-officedocument.presentationml.presentation": PdfPreviewViewer,
};
