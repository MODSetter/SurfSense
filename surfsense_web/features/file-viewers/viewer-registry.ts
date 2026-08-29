"use client";

import dynamic from "next/dynamic";
import { type ComponentType, createElement } from "react";
import { Spinner } from "@/components/ui/spinner";
import type { FileViewerProps } from "./model";

export function FileViewerLoading() {
	return createElement(
		"div",
		{ className: "flex h-full items-center justify-center" },
		createElement(Spinner, { size: "lg" })
	);
}

const PdfFileViewer = dynamic<FileViewerProps>(() => import("./pdf-file-viewer"), {
	ssr: false,
	loading: FileViewerLoading,
});
const XlsxViewer = dynamic<FileViewerProps>(() => import("./xlsx-viewer"), {
	ssr: false,
	loading: FileViewerLoading,
});

/** Direct viewers render the file itself; domain-specific preview adapters remain with their owner. */
export const FILE_VIEWERS: Readonly<Partial<Record<string, ComponentType<FileViewerProps>>>> = {
	"application/pdf": PdfFileViewer,
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": XlsxViewer,
};
