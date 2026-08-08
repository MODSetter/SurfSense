"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { ArtifactFile } from "./model";

export interface ArtifactFileViewerProps {
	primary: ArtifactFile;
	files: ArtifactFile[];
}

const PdfFileViewer = dynamic<ArtifactFileViewerProps>(() => import("./pdf-file-viewer"), {
	ssr: false,
});

// Unknown MIME types deliberately fall through to FileDownloadCard.
export const VIEWERS: Partial<Record<string, ComponentType<ArtifactFileViewerProps>>> = {
	"application/pdf": PdfFileViewer,
};
