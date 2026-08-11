"use client";

import { PdfViewer } from "@/components/shared/pdf-viewer";
import { buildBackendUrl } from "@/lib/env-config";
import { cannotPreviewMessage } from "./file-format";
import { UnviewableArtifact } from "./unviewable-artifact";
import type { ArtifactFileViewerProps } from "./viewer-registry";

export default function PdfPreviewViewer({ primary, files }: ArtifactFileViewerProps) {
	const preview = files.find((file) => file.role === "preview");
	if (!preview) {
		return <UnviewableArtifact message={cannotPreviewMessage(primary.filename)} />;
	}
	return <PdfViewer pdfUrl={buildBackendUrl(preview.content_url)} />;
}
