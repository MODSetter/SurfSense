"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { FileQuestionMark, XIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";
import {
	closeDocumentViewerAtom,
	documentViewerAtom,
} from "@/atoms/documents/document-viewer.atom";
import { DownloadOriginalButton } from "@/components/documents/download-original-button";
import { VersionHistoryButton } from "@/components/documents/version-history";
import { PlateErrorBoundary } from "@/components/editor/plate-error-boundary";
import { SourceCodeEditor } from "@/components/editor/source-code-editor";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { extension } from "@/features/file-viewers/file-format";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";
import { FILE_VIEWERS } from "@/features/file-viewers/viewer-registry";
import { useMediaQuery } from "@/hooks/use-media-query";
import { documentContentQueryOptions } from "./document-content-query";
import { documentViewQueryOptions } from "./document-view-query";
import type { DocumentViewManifest } from "./model";

const PlateEditor = dynamic(
	() => import("@/components/editor/plate-editor").then((module) => module.PlateEditor),
	{ ssr: false, loading: () => <DocumentLoading /> }
);

const ignoreMarkdownChange = () => {};

function DocumentLoading() {
	return (
		<div aria-busy="true" className="flex h-full items-center justify-center">
			<Spinner size="lg" />
		</div>
	);
}

function MarkdownDocument({
	workspaceId,
	documentId,
}: {
	workspaceId: number;
	documentId: number;
}) {
	const { data, error, isPending, refetch } = useQuery(
		documentContentQueryOptions(workspaceId, documentId)
	);

	if (isPending) return <DocumentLoading />;
	if (error || !data) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
				<FileQuestionMark className="size-7 text-muted-foreground" />
				<p className="max-w-xs text-sm text-muted-foreground">
					{error instanceof Error ? error.message : "Document unavailable"}
				</p>
				<Button variant="secondary" size="sm" onClick={() => void refetch()}>
					Try again
				</Button>
			</div>
		);
	}

	if (data.viewer_mode === "monaco") {
		return (
			<SourceCodeEditor
				path={`${data.title || "document"}.md`}
				language="markdown"
				value={data.source_markdown}
				readOnly
				onChange={ignoreMarkdownChange}
			/>
		);
	}

	return (
		<PlateErrorBoundary
			fallback={
				<SourceCodeEditor
					path={`${data.title || "document"}.md`}
					language="markdown"
					value={data.source_markdown}
					readOnly
					onChange={ignoreMarkdownChange}
				/>
			}
		>
			<PlateEditor
				preset="full"
				markdown={data.source_markdown}
				onMarkdownChange={ignoreMarkdownChange}
				readOnly
				placeholder=""
				editorVariant="default"
				allowModeToggle={false}
				reserveToolbarSpace={false}
				defaultEditing={false}
				enableCitations
				className="**:[[role=toolbar]]:bg-sidebar!"
			/>
		</PlateErrorBoundary>
	);
}

function DocumentHeader({
	manifest,
	title,
	documentId,
	workspaceId,
	onClose,
	zoomControlsContainerRef,
}: {
	manifest?: DocumentViewManifest;
	title: string;
	documentId: number;
	workspaceId: number;
	onClose?: () => void;
	zoomControlsContainerRef: (node: HTMLDivElement | null) => void;
}) {
	const file = manifest?.file;
	return (
		<div className="grid h-12 shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-4">
			<div className="flex min-w-0 items-center gap-2">
				<p className="truncate text-sm text-muted-foreground">{manifest?.title ?? title}</p>
				{file ? (
					<span className="shrink-0 text-xs text-muted-foreground">
						{extension(file.filename)}
					</span>
				) : null}
			</div>
			<div className="flex shrink-0 items-center gap-1">
				<div ref={zoomControlsContainerRef} className="flex items-center gap-1" />
				{manifest?.document_type ? (
					<VersionHistoryButton
						documentId={documentId}
						documentType={manifest.document_type}
					/>
				) : null}
				<DownloadOriginalButton documentId={documentId} workspaceId={workspaceId} />
				{onClose ? (
					<>
						<Separator
							orientation="vertical"
							className="mx-1.5 bg-muted-foreground/20 data-[orientation=vertical]:h-4 data-[orientation=vertical]:w-px dark:bg-muted-foreground/25"
						/>
						<Button
							variant="ghost"
							size="icon"
							onClick={onClose}
							className="size-6 shrink-0 rounded-full text-muted-foreground"
						>
							<XIcon className="size-4" />
							<span className="sr-only">Close document panel</span>
						</Button>
					</>
				) : null}
			</div>
		</div>
	);
}

export function DocumentViewerContent({
	workspaceId,
	documentId,
	title,
	onClose,
}: {
	workspaceId: number;
	documentId: number;
	title: string;
	onClose?: () => void;
}) {
	const [zoomControlsContainer, setZoomControlsContainer] = useState<HTMLDivElement | null>(null);
	const { data: manifest, error, isPending, refetch } = useQuery(
		documentViewQueryOptions(workspaceId, documentId)
	);
	const file = manifest?.file;
	const Viewer = file ? FILE_VIEWERS[file.mime_type] : undefined;

	return (
		<div className="flex h-full min-h-0 flex-col">
			<DocumentHeader
				manifest={manifest}
				title={title}
				documentId={documentId}
				workspaceId={workspaceId}
				onClose={onClose}
				zoomControlsContainerRef={setZoomControlsContainer}
			/>
			<div className="min-h-0 flex-1 overflow-hidden">
				{isPending ? (
					<DocumentLoading />
				) : error || !manifest ? (
					<div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
						<FileQuestionMark className="size-7 text-muted-foreground" />
						<p className="max-w-xs text-sm text-muted-foreground">
							{error instanceof Error ? error.message : "Document unavailable"}
						</p>
						<Button variant="secondary" size="sm" onClick={() => void refetch()}>
							Try again
						</Button>
					</div>
				) : manifest.presentation === "text" ? (
					<MarkdownDocument workspaceId={workspaceId} documentId={documentId} />
				) : manifest.presentation === "missing_original" ? (
					<UnviewableFile
						message={
							manifest.status === "pending" || manifest.status === "processing"
								? "The original file is still being prepared."
								: "The original file is unavailable. Re-upload this document to preview it."
						}
					/>
				) : file && Viewer ? (
					<Viewer
						primary={file}
						files={[file]}
						zoomControlsContainer={zoomControlsContainer}
					/>
				) : (
					<UnviewableFile message="This original file format cannot be previewed." />
				)}
			</div>
		</div>
	);
}

function MobileDocumentDrawer() {
	const state = useAtomValue(documentViewerAtom);
	const close = useSetAtom(closeDocumentViewerAtom);
	if (!state.documentId || !state.workspaceId) return null;

	return (
		<Drawer open={state.isOpen} onOpenChange={(open) => !open && close()} shouldScaleBackground={false}>
			<DrawerContent className="z-80 h-[90vh] max-h-[90vh] overflow-hidden bg-sidebar" overlayClassName="z-80">
				<DrawerHandle />
				<DrawerTitle className="sr-only">{state.title || "Document"}</DrawerTitle>
				<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
					<DocumentViewerContent
						workspaceId={state.workspaceId}
						documentId={state.documentId}
						title={state.title}
					/>
				</div>
			</DrawerContent>
		</Drawer>
	);
}

export function MobileDocumentViewerPanel() {
	const state = useAtomValue(documentViewerAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	if (isDesktop || !state.isOpen || !state.documentId || !state.workspaceId) return null;
	return <MobileDocumentDrawer />;
}
