"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { FileViewerProps } from "@/features/file-viewers/model";
import {
	FILE_VIEWERS,
	FileViewerLoading,
} from "@/features/file-viewers/viewer-registry";

const PdfPreviewViewer = dynamic<FileViewerProps>(() => import("./pdf-preview-viewer"), {
	ssr: false,
	loading: FileViewerLoading,
});

// Unknown MIME types deliberately fall through to the panel's unviewable state,
// where the header's download button is still the way out.
export const VIEWERS: Readonly<Partial<Record<string, ComponentType<FileViewerProps>>>> = {
	...FILE_VIEWERS,
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document": PdfPreviewViewer,
	"application/vnd.openxmlformats-officedocument.presentationml.presentation": PdfPreviewViewer,
};
