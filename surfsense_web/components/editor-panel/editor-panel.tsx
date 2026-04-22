"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Download, FileQuestionMark, FileText, RefreshCw, XIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { closeEditorPanelAtom, editorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { VersionHistoryButton } from "@/components/documents/version-history";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Spinner } from "@/components/ui/spinner";
import { useMediaQuery } from "@/hooks/use-media-query";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";

const PlateEditor = dynamic(
	() => import("@/components/editor/plate-editor").then((m) => ({ default: m.PlateEditor })),
	{ ssr: false, loading: () => <EditorPanelSkeleton /> }
);

const LARGE_DOCUMENT_THRESHOLD = 2 * 1024 * 1024; // 2MB

interface EditorContent {
	document_id: number;
	title: string;
	document_type?: string;
	source_markdown: string;
	content_size_bytes?: number;
	chunk_count?: number;
	truncated?: boolean;
}

const EDITABLE_DOCUMENT_TYPES = new Set(["FILE", "NOTE"]);

function EditorPanelSkeleton() {
	return (
		<div className="space-y-6 p-6">
			<div className="h-6 w-3/4 rounded-md bg-muted/60 animate-pulse" />
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse" />
				<div className="h-3 w-[95%] rounded-md bg-muted/60 animate-pulse [animation-delay:100ms]" />
				<div className="h-3 w-[88%] rounded-md bg-muted/60 animate-pulse [animation-delay:200ms]" />
				<div className="h-3 w-[60%] rounded-md bg-muted/60 animate-pulse [animation-delay:300ms]" />
			</div>
			<div className="h-5 w-2/5 rounded-md bg-muted/60 animate-pulse [animation-delay:400ms]" />
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:500ms]" />
				<div className="h-3 w-[92%] rounded-md bg-muted/60 animate-pulse [animation-delay:600ms]" />
				<div className="h-3 w-[75%] rounded-md bg-muted/60 animate-pulse [animation-delay:700ms]" />
			</div>
		</div>
	);
}

export function EditorPanelContent({
	documentId,
	searchSpaceId,
	title,
	onClose,
}: {
	documentId: number;
	searchSpaceId: number;
	title: string | null;
	onClose?: () => void;
}) {
	const [editorDoc, setEditorDoc] = useState<EditorContent | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);
	const [downloading, setDownloading] = useState(false);

	const [editedMarkdown, setEditedMarkdown] = useState<string | null>(null);
	const markdownRef = useRef<string>("");
	const initialLoadDone = useRef(false);
	const changeCountRef = useRef(0);
	const [displayTitle, setDisplayTitle] = useState(title || "Untitled");

	const isLargeDocument = (editorDoc?.content_size_bytes ?? 0) > LARGE_DOCUMENT_THRESHOLD;

	useEffect(() => {
		const controller = new AbortController();
		setIsLoading(true);
		setError(null);
		setEditorDoc(null);
		setEditedMarkdown(null);
		initialLoadDone.current = false;
		changeCountRef.current = 0;

		const doFetch = async () => {
			const token = getBearerToken();
			if (!token) {
				redirectToLogin();
				return;
			}

			try {
				const url = new URL(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/editor-content`
				);
				url.searchParams.set("max_length", String(LARGE_DOCUMENT_THRESHOLD));

				const response = await authenticatedFetch(url.toString(), { method: "GET" });

				if (controller.signal.aborted) return;

				if (!response.ok) {
					const errorData = await response
						.json()
						.catch(() => ({ detail: "Failed to fetch document" }));
					throw new Error(errorData.detail || "Failed to fetch document");
				}

				const data = await response.json();

				if (data.source_markdown === undefined || data.source_markdown === null) {
					setError(
						"This document does not have editable content. Please re-upload to enable editing."
					);
					setIsLoading(false);
					return;
				}

				markdownRef.current = data.source_markdown;
				setDisplayTitle(data.title || title || "Untitled");
				setEditorDoc(data);
				initialLoadDone.current = true;
			} catch (err) {
				if (controller.signal.aborted) return;
				console.error("Error fetching document:", err);
				setError(err instanceof Error ? err.message : "Failed to fetch document");
			} finally {
				if (!controller.signal.aborted) setIsLoading(false);
			}
		};

		doFetch().catch(() => {});
		return () => controller.abort();
	}, [documentId, searchSpaceId, title]);

	const handleMarkdownChange = useCallback((md: string) => {
		markdownRef.current = md;
		if (!initialLoadDone.current) return;
		changeCountRef.current += 1;
		if (changeCountRef.current <= 1) return;
		setEditedMarkdown(md);
	}, []);

	const handleSave = useCallback(async () => {
		const token = getBearerToken();
		if (!token) {
			toast.error("Please login to save");
			redirectToLogin();
			return;
		}

		setSaving(true);
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/save`,
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ source_markdown: markdownRef.current }),
				}
			);

			if (!response.ok) {
				const errorData = await response
					.json()
					.catch(() => ({ detail: "Failed to save document" }));
				throw new Error(errorData.detail || "Failed to save document");
			}

			setEditorDoc((prev) => (prev ? { ...prev, source_markdown: markdownRef.current } : prev));
			setEditedMarkdown(null);
			toast.success("Document saved! Reindexing in background...");
		} catch (err) {
			console.error("Error saving document:", err);
			toast.error(err instanceof Error ? err.message : "Failed to save document");
		} finally {
			setSaving(false);
		}
	}, [documentId, searchSpaceId]);

	const isEditableType = editorDoc
		? EDITABLE_DOCUMENT_TYPES.has(editorDoc.document_type ?? "") && !isLargeDocument
		: false;

	return (
		<>
			<div className="flex items-center justify-between px-4 py-2 shrink-0 border-b">
				<div className="flex-1 min-w-0">
					<h2 className="text-sm font-semibold truncate">{displayTitle}</h2>
					{isEditableType && editedMarkdown !== null && (
						<p className="text-[10px] text-muted-foreground">Unsaved changes</p>
					)}
				</div>
				<div className="flex items-center gap-1 shrink-0">
					{editorDoc?.document_type && (
						<VersionHistoryButton documentId={documentId} documentType={editorDoc.document_type} />
					)}
					{onClose && (
						<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
							<XIcon className="size-4" />
							<span className="sr-only">Close editor panel</span>
						</Button>
					)}
				</div>
			</div>

			<div className="flex-1 overflow-hidden">
				{isLoading ? (
					<EditorPanelSkeleton />
				) : error || !editorDoc ? (
					<div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
						{error?.toLowerCase().includes("still being processed") ? (
							<div className="rounded-full bg-muted/50 p-3">
								<RefreshCw className="size-6 text-muted-foreground animate-spin" />
							</div>
						) : (
							<div className="rounded-full bg-muted/50 p-3">
								<FileQuestionMark className="size-6 text-muted-foreground" />
							</div>
						)}
						<div className="space-y-1 max-w-xs">
							<p className="font-medium text-foreground">
								{error?.toLowerCase().includes("still being processed")
									? "Document is processing"
									: "Document unavailable"}
							</p>
							<p className="text-sm text-muted-foreground">
								{error || "An unknown error occurred"}
							</p>
						</div>
					</div>
				) : isLargeDocument ? (
					<div className="h-full overflow-y-auto px-5 py-4">
						<Alert className="mb-4">
							<FileText className="size-4" />
							<AlertDescription className="flex items-center justify-between gap-4">
								<span>
									This document is too large for the editor (
									{Math.round((editorDoc.content_size_bytes ?? 0) / 1024 / 1024)}MB,{" "}
									{editorDoc.chunk_count ?? 0} chunks). Showing a preview below.
								</span>
								<Button
									variant="outline"
									size="sm"
									className="relative shrink-0"
									disabled={downloading}
									onClick={async () => {
										setDownloading(true);
										try {
											const response = await authenticatedFetch(
												`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/download-markdown`,
												{ method: "GET" }
											);
											if (!response.ok) throw new Error("Download failed");
											const blob = await response.blob();
											const url = URL.createObjectURL(blob);
											const a = document.createElement("a");
											a.href = url;
											const disposition = response.headers.get("content-disposition");
											const match = disposition?.match(/filename="(.+)"/);
											a.download = match?.[1] ?? `${editorDoc.title || "document"}.md`;
											document.body.appendChild(a);
											a.click();
											a.remove();
											URL.revokeObjectURL(url);
											toast.success("Download started");
										} catch {
											toast.error("Failed to download document");
										} finally {
											setDownloading(false);
										}
									}}
								>
									<span
										className={`flex items-center gap-1.5 ${downloading ? "opacity-0" : ""}`}
									>
										<Download className="size-3.5" />
										Download .md
									</span>
									{downloading && <Spinner size="sm" className="absolute" />}
								</Button>
							</AlertDescription>
						</Alert>
						<MarkdownViewer content={editorDoc.source_markdown} />
					</div>
				) : isEditableType ? (
					<PlateEditor
						key={documentId}
						preset="full"
						markdown={editorDoc.source_markdown}
						onMarkdownChange={handleMarkdownChange}
						readOnly={false}
						placeholder="Start writing..."
						editorVariant="default"
						onSave={handleSave}
						hasUnsavedChanges={editedMarkdown !== null}
						isSaving={saving}
						defaultEditing={true}
						className="[&_[role=toolbar]]:!bg-sidebar"
					/>
				) : (
					<div className="h-full overflow-y-auto px-5 py-4">
						<MarkdownViewer content={editorDoc.source_markdown} />
					</div>
				)}
			</div>
		</>
	);
}

function DesktopEditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const closePanel = useSetAtom(closeEditorPanelAtom);

	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") closePanel();
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [closePanel]);

	if (!panelState.isOpen || !panelState.documentId || !panelState.searchSpaceId) return null;

	return (
		<div className="flex w-[50%] max-w-[700px] min-w-[380px] flex-col border-l bg-sidebar text-sidebar-foreground animate-in slide-in-from-right-4 duration-300 ease-out">
			<EditorPanelContent
				documentId={panelState.documentId}
				searchSpaceId={panelState.searchSpaceId}
				title={panelState.title}
				onClose={closePanel}
			/>
		</div>
	);
}

function MobileEditorDrawer() {
	const panelState = useAtomValue(editorPanelAtom);
	const closePanel = useSetAtom(closeEditorPanelAtom);

	if (!panelState.documentId || !panelState.searchSpaceId) return null;

	return (
		<Drawer
			open={panelState.isOpen}
			onOpenChange={(open) => {
				if (!open) closePanel();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[90vh] max-h-[90vh] z-80 bg-sidebar overflow-hidden"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">{panelState.title || "Editor"}</DrawerTitle>
				<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
					<EditorPanelContent
						documentId={panelState.documentId}
						searchSpaceId={panelState.searchSpaceId}
						title={panelState.title}
					/>
				</div>
			</DrawerContent>
		</Drawer>
	);
}

export function EditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (!panelState.isOpen || !panelState.documentId) return null;

	if (isDesktop) {
		return <DesktopEditorPanel />;
	}

	return <MobileEditorDrawer />;
}

export function MobileEditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !panelState.isOpen || !panelState.documentId) return null;

	return <MobileEditorDrawer />;
}
