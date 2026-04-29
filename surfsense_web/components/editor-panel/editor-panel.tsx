"use client";

import { useAtomValue, useSetAtom } from "jotai";
import {
	Check,
	Copy,
	Download,
	FileQuestionMark,
	FileText,
	Pencil,
	RefreshCw,
	XIcon,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { closeEditorPanelAtom, editorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { VersionHistoryButton } from "@/components/documents/version-history";
import { SourceCodeEditor } from "@/components/editor/source-code-editor";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Spinner } from "@/components/ui/spinner";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";
import { inferMonacoLanguageFromPath } from "@/lib/editor-language";

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
type EditorRenderMode = "rich_markdown" | "source_code";

type AgentFilesystemMount = {
	mount: string;
	rootPath: string;
};

function normalizeLocalVirtualPathForEditor(
	candidatePath: string,
	mounts: AgentFilesystemMount[]
): string {
	const normalizedCandidate = candidatePath.trim().replace(/\\/g, "/").replace(/\/+/g, "/");
	if (!normalizedCandidate) return candidatePath;
	const defaultMount = mounts[0]?.mount;
	if (!defaultMount) {
		return normalizedCandidate.startsWith("/")
			? normalizedCandidate
			: `/${normalizedCandidate.replace(/^\/+/, "")}`;
	}

	const mountNames = new Set(mounts.map((entry) => entry.mount));
	if (normalizedCandidate.startsWith("/")) {
		const relative = normalizedCandidate.replace(/^\/+/, "");
		const [firstSegment] = relative.split("/", 1);
		if (mountNames.has(firstSegment)) {
			return `/${relative}`;
		}
		return `/${defaultMount}/${relative}`;
	}

	const relative = normalizedCandidate.replace(/^\/+/, "");
	const [firstSegment] = relative.split("/", 1);
	if (mountNames.has(firstSegment)) {
		return `/${relative}`;
	}
	return `/${defaultMount}/${relative}`;
}

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
	kind = "document",
	documentId,
	localFilePath,
	searchSpaceId,
	title,
	onClose,
}: {
	kind?: "document" | "local_file";
	documentId?: number;
	localFilePath?: string;
	searchSpaceId?: number;
	title: string | null;
	onClose?: () => void;
}) {
	const electronAPI = useElectronAPI();
	const [editorDoc, setEditorDoc] = useState<EditorContent | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);
	const [downloading, setDownloading] = useState(false);
	const [isEditing, setIsEditing] = useState(false);

	const [editedMarkdown, setEditedMarkdown] = useState<string | null>(null);
	const [localFileContent, setLocalFileContent] = useState("");
	const [hasCopied, setHasCopied] = useState(false);
	const markdownRef = useRef<string>("");
	const copyResetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const initialLoadDone = useRef(false);
	const changeCountRef = useRef(0);
	const [displayTitle, setDisplayTitle] = useState(title || "Untitled");
	const isLocalFileMode = kind === "local_file";
	const editorRenderMode: EditorRenderMode = isLocalFileMode ? "source_code" : "rich_markdown";

	const resolveLocalVirtualPath = useCallback(
		async (candidatePath: string): Promise<string> => {
			if (!electronAPI?.getAgentFilesystemMounts) {
				return candidatePath;
			}
			try {
				const mounts = (await electronAPI.getAgentFilesystemMounts(
					searchSpaceId
				)) as AgentFilesystemMount[];
				return normalizeLocalVirtualPathForEditor(candidatePath, mounts);
			} catch {
				return candidatePath;
			}
		},
		[electronAPI, searchSpaceId]
	);

	const isLargeDocument = (editorDoc?.content_size_bytes ?? 0) > LARGE_DOCUMENT_THRESHOLD;

	useEffect(() => {
		const controller = new AbortController();
		setIsLoading(true);
		setError(null);
		setEditorDoc(null);
		setEditedMarkdown(null);
		setLocalFileContent("");
		setHasCopied(false);
		setIsEditing(false);
		initialLoadDone.current = false;
		changeCountRef.current = 0;

		const doFetch = async () => {
			try {
				if (isLocalFileMode) {
					if (!localFilePath) {
						throw new Error("Missing local file path");
					}
					if (!electronAPI?.readAgentLocalFileText) {
						throw new Error("Local file editor is available only in desktop mode.");
					}
					const resolvedLocalPath = await resolveLocalVirtualPath(localFilePath);
					const readResult = await electronAPI.readAgentLocalFileText(
						resolvedLocalPath,
						searchSpaceId
					);
					if (!readResult.ok) {
						throw new Error(readResult.error || "Failed to read local file");
					}
					const inferredTitle = resolvedLocalPath.split("/").pop() || resolvedLocalPath;
					const content: EditorContent = {
						document_id: -1,
						title: inferredTitle,
						document_type: "NOTE",
						source_markdown: readResult.content,
					};
					markdownRef.current = content.source_markdown;
					setLocalFileContent(content.source_markdown);
					setDisplayTitle(title || inferredTitle);
					setEditorDoc(content);
					initialLoadDone.current = true;
					return;
				}
				if (!documentId || !searchSpaceId) {
					throw new Error("Missing document context");
				}
				const token = getBearerToken();
				if (!token) {
					redirectToLogin();
					return;
				}

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
	}, [
		documentId,
		electronAPI,
		isLocalFileMode,
		localFilePath,
		resolveLocalVirtualPath,
		searchSpaceId,
		title,
	]);

	useEffect(() => {
		return () => {
			if (copyResetTimeoutRef.current) {
				clearTimeout(copyResetTimeoutRef.current);
			}
		};
	}, []);

	const handleMarkdownChange = useCallback((md: string) => {
		markdownRef.current = md;
		if (!initialLoadDone.current) return;
		changeCountRef.current += 1;
		if (changeCountRef.current <= 1) return;
		setEditedMarkdown(md);
	}, []);

	const handleCopy = useCallback(async () => {
		try {
			const textToCopy = markdownRef.current ?? editorDoc?.source_markdown ?? "";
			await navigator.clipboard.writeText(textToCopy);
			setHasCopied(true);
			if (copyResetTimeoutRef.current) {
				clearTimeout(copyResetTimeoutRef.current);
			}
			copyResetTimeoutRef.current = setTimeout(() => {
				setHasCopied(false);
			}, 1400);
		} catch (err) {
			console.error("Error copying content:", err);
		}
	}, [editorDoc?.source_markdown]);

	const handleSave = useCallback(
		async (options?: { silent?: boolean }) => {
			setSaving(true);
			try {
				if (isLocalFileMode) {
					if (!localFilePath) {
						throw new Error("Missing local file path");
					}
					if (!electronAPI?.writeAgentLocalFileText) {
						throw new Error("Local file editor is available only in desktop mode.");
					}
					const resolvedLocalPath = await resolveLocalVirtualPath(localFilePath);
					const contentToSave = markdownRef.current;
					const writeResult = await electronAPI.writeAgentLocalFileText(
						resolvedLocalPath,
						contentToSave,
						searchSpaceId
					);
					if (!writeResult.ok) {
						throw new Error(writeResult.error || "Failed to save local file");
					}
					setEditorDoc((prev) => (prev ? { ...prev, source_markdown: contentToSave } : prev));
					setEditedMarkdown(markdownRef.current === contentToSave ? null : markdownRef.current);
					return true;
				}
				if (!searchSpaceId || !documentId) {
					throw new Error("Missing document context");
				}
				const token = getBearerToken();
				if (!token) {
					toast.error("Please login to save");
					redirectToLogin();
					return;
				}
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
				if (!options?.silent) {
					toast.success("Document saved! Reindexing in background...");
				}
				return true;
			} catch (err) {
				console.error("Error saving document:", err);
				if (!options?.silent) {
					toast.error(err instanceof Error ? err.message : "Failed to save document");
				}
				return false;
			} finally {
				setSaving(false);
			}
		},
		[
			documentId,
			electronAPI,
			isLocalFileMode,
			localFilePath,
			resolveLocalVirtualPath,
			searchSpaceId,
		]
	);

	const isEditableType = editorDoc
		? (editorRenderMode === "source_code" ||
				EDITABLE_DOCUMENT_TYPES.has(editorDoc.document_type ?? "")) &&
			!isLargeDocument
		: false;
	// Render through PlateEditor for editable doc types (FILE/NOTE).
	// Everything else (large docs, non-editable types) falls back to the
	// lightweight `MarkdownViewer` — Plate is heavy on multi-MB docs and
	// non-editable types don't benefit from its editing UX.
	const renderInPlateEditor = isEditableType;
	const hasUnsavedChanges = editedMarkdown !== null;
	const showDesktopHeader = !!onClose;
	const showEditingActions = isEditableType && isEditing;
	const localFileLanguage = inferMonacoLanguageFromPath(localFilePath);

	const handleCancelEditing = useCallback(() => {
		const savedContent = editorDoc?.source_markdown ?? "";
		markdownRef.current = savedContent;
		setLocalFileContent(savedContent);
		setEditedMarkdown(null);
		changeCountRef.current = 0;
		setIsEditing(false);
	}, [editorDoc?.source_markdown]);

	const handleDownloadMarkdown = useCallback(async () => {
		if (!searchSpaceId || !documentId) return;
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
			a.download = match?.[1] ?? `${editorDoc?.title || "document"}.md`;
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
	}, [documentId, editorDoc?.title, searchSpaceId]);

	const largeDocAlert = isLargeDocument && !isLocalFileMode && editorDoc && (
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
					onClick={handleDownloadMarkdown}
				>
					<span className={`flex items-center gap-1.5 ${downloading ? "opacity-0" : ""}`}>
						<Download className="size-3.5" />
						Download .md
					</span>
					{downloading && <Spinner size="sm" className="absolute" />}
				</Button>
			</AlertDescription>
		</Alert>
	);

	return (
		<>
			{showDesktopHeader ? (
				<div className="shrink-0 border-b">
					<div className="flex h-14 items-center justify-between px-4">
						<h2 className="text-lg font-medium text-muted-foreground select-none">File</h2>
						<div className="flex items-center gap-1 shrink-0">
							<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
								<XIcon className="size-4" />
								<span className="sr-only">Close editor panel</span>
							</Button>
						</div>
					</div>
					<div className="flex h-10 items-center justify-between gap-2 border-t px-4">
						<div className="min-w-0 flex flex-1 items-center gap-2">
							<p className="truncate text-sm text-muted-foreground">{displayTitle}</p>
						</div>
						<div className="flex items-center gap-1 shrink-0">
							{showEditingActions ? (
								<>
									<Button
										variant="ghost"
										size="sm"
										className="h-6 px-2 text-xs"
										onClick={handleCancelEditing}
										disabled={saving}
									>
										Cancel
									</Button>
									<Button
										variant="secondary"
										size="sm"
										className="relative h-6 w-[56px] px-0 text-xs"
										onClick={async () => {
											const saveSucceeded = await handleSave({ silent: true });
											if (saveSucceeded) setIsEditing(false);
										}}
										disabled={saving || !hasUnsavedChanges}
									>
										<span className={saving ? "opacity-0" : ""}>Save</span>
										{saving && <Spinner size="xs" className="absolute" />}
									</Button>
								</>
							) : (
								<>
									{!isLocalFileMode && editorDoc?.document_type && documentId && (
										<VersionHistoryButton
											documentId={documentId}
											documentType={editorDoc.document_type}
										/>
									)}
									<Button
										variant="ghost"
										size="icon"
										className="size-6"
										onClick={() => {
											void handleCopy();
										}}
										disabled={isLoading || !editorDoc}
									>
										{hasCopied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
										<span className="sr-only">
											{hasCopied ? "Copied file contents" : "Copy file contents"}
										</span>
									</Button>
									{isEditableType && (
										<Button
											variant="ghost"
											size="icon"
											className="size-6"
											onClick={() => {
												changeCountRef.current = 0;
												setEditedMarkdown(null);
												setIsEditing(true);
											}}
										>
											<Pencil className="size-3.5" />
											<span className="sr-only">Edit document</span>
										</Button>
									)}
								</>
							)}
						</div>
					</div>
				</div>
			) : (
				<div className="flex h-14 items-center justify-between border-b px-4 shrink-0">
					<div className="flex flex-1 min-w-0 items-center gap-2">
						<h2 className="text-sm font-semibold truncate">{displayTitle}</h2>
					</div>
					<div className="flex items-center gap-1 shrink-0">
						{showEditingActions ? (
							<>
								<Button
									variant="ghost"
									size="sm"
									className="h-6 px-2 text-xs"
									onClick={handleCancelEditing}
									disabled={saving}
								>
									Cancel
								</Button>
								<Button
									variant="secondary"
									size="sm"
									className="relative h-6 w-[56px] px-0 text-xs"
									onClick={async () => {
										const saveSucceeded = await handleSave({ silent: true });
										if (saveSucceeded) setIsEditing(false);
									}}
									disabled={saving || !hasUnsavedChanges}
								>
									<span className={saving ? "opacity-0" : ""}>Save</span>
									{saving && <Spinner size="xs" className="absolute" />}
								</Button>
							</>
						) : (
							<>
								{!isLocalFileMode && editorDoc?.document_type && documentId && (
									<VersionHistoryButton
										documentId={documentId}
										documentType={editorDoc.document_type}
									/>
								)}
								<Button
									variant="ghost"
									size="icon"
									className="size-6"
									onClick={() => {
										void handleCopy();
									}}
									disabled={isLoading || !editorDoc}
								>
									{hasCopied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
									<span className="sr-only">
										{hasCopied ? "Copied file contents" : "Copy file contents"}
									</span>
								</Button>
								{isEditableType && (
									<Button
										variant="ghost"
										size="icon"
										className="size-6"
										onClick={() => {
											changeCountRef.current = 0;
											setEditedMarkdown(null);
											setIsEditing(true);
										}}
									>
										<Pencil className="size-3.5" />
										<span className="sr-only">Edit document</span>
									</Button>
								)}
							</>
						)}
					</div>
				</div>
			)}

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
				) : editorRenderMode === "source_code" ? (
					<div className="h-full overflow-hidden">
						<SourceCodeEditor
							path={localFilePath ?? "local-file.txt"}
							language={localFileLanguage}
							value={localFileContent}
							onSave={() => {
								void handleSave({ silent: true });
							}}
							readOnly={!isEditing}
							onChange={(next) => {
								markdownRef.current = next;
								setLocalFileContent(next);
								if (!initialLoadDone.current) return;
								setEditedMarkdown(next === (editorDoc?.source_markdown ?? "") ? null : next);
							}}
						/>
					</div>
				) : isLargeDocument && !isLocalFileMode ? (
					// Large doc — fast Streamdown preview + download CTA.
					// Plate is heavy on multi-MB docs.
					<div className="h-full overflow-y-auto px-5 py-4">
						{largeDocAlert}
						<MarkdownViewer content={editorDoc.source_markdown} />
					</div>
				) : renderInPlateEditor ? (
					// Editable doc (FILE/NOTE) — Plate editing UX.
					<div className="flex h-full min-h-0 flex-col">
						<div className="flex-1 min-h-0 overflow-hidden">
							<PlateEditor
								key={`${isLocalFileMode ? (localFilePath ?? "local-file") : documentId}-${isEditing ? "editing" : "viewing"}`}
								preset="full"
								markdown={editorDoc.source_markdown}
								onMarkdownChange={handleMarkdownChange}
								readOnly={!isEditing}
								placeholder="Start writing..."
								editorVariant="default"
								allowModeToggle={false}
								reserveToolbarSpace
								defaultEditing={isEditing}
								className="**:[[role=toolbar]]:bg-sidebar!"
							/>
						</div>
					</div>
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

	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;
	if (!panelState.isOpen || !hasTarget) return null;

	return (
		<div className="flex w-[50%] max-w-[700px] min-w-[380px] flex-col border-l bg-sidebar text-sidebar-foreground animate-in slide-in-from-right-4 duration-300 ease-out">
			<EditorPanelContent
				kind={panelState.kind}
				documentId={panelState.documentId ?? undefined}
				localFilePath={panelState.localFilePath ?? undefined}
				searchSpaceId={panelState.searchSpaceId ?? undefined}
				title={panelState.title}
				onClose={closePanel}
			/>
		</div>
	);
}

function MobileEditorDrawer() {
	const panelState = useAtomValue(editorPanelAtom);
	const closePanel = useSetAtom(closeEditorPanelAtom);

	if (panelState.kind === "local_file") return null;

	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;
	if (!hasTarget) return null;

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
						kind={panelState.kind}
						documentId={panelState.documentId ?? undefined}
						localFilePath={panelState.localFilePath ?? undefined}
						searchSpaceId={panelState.searchSpaceId ?? undefined}
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
	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;

	if (!panelState.isOpen || !hasTarget) return null;
	if (!isDesktop && panelState.kind === "local_file") return null;

	if (isDesktop) {
		return <DesktopEditorPanel />;
	}

	return <MobileEditorDrawer />;
}

export function MobileEditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;

	if (isDesktop || !panelState.isOpen || !hasTarget || panelState.kind === "local_file")
		return null;

	return <MobileEditorDrawer />;
}
