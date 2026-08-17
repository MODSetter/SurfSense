"use client";

import dynamic from "next/dynamic";
import { createElement, type ComponentType } from "react";
import { Spinner } from "@/components/ui/spinner";
import type { ArtifactFile } from "./model";

export interface ArtifactFileViewerProps {
	primary: ArtifactFile;
	files: ArtifactFile[];
	zoomControlsContainer?: HTMLElement | null;
}

function ViewerLoading() {
	return createElement(
		"div",
		{ className: "flex h-full items-center justify-center" },
		createElement(Spinner, { size: "lg" })
	);
}

const PdfFileViewer = dynamic<ArtifactFileViewerProps>(() => import("./pdf-file-viewer"), {
	ssr: false,
	loading: ViewerLoading,
});
const PdfPreviewViewer = dynamic<ArtifactFileViewerProps>(() => import("./pdf-preview-viewer"), {
	ssr: false,
	loading: ViewerLoading,
});
const XlsxViewer = dynamic<ArtifactFileViewerProps>(() => import("./xlsx-viewer"), {
	ssr: false,
	loading: ViewerLoading,
});

// Unknown MIME types deliberately fall through to the panel's unviewable state,
// where the header's download button is still the way out.
export const VIEWERS: Partial<Record<string, ComponentType<ArtifactFileViewerProps>>> = {
	"application/pdf": PdfFileViewer,
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document": PdfPreviewViewer,
	"application/vnd.openxmlformats-officedocument.presentationml.presentation": PdfPreviewViewer,
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": XlsxViewer,
};
