"use client";

import { Download, FileQuestionMark, FileText, PenLine, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { PlateEditor } from "@/components/editor/plate-editor";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";

const LARGE_DOCUMENT_THRESHOLD = 2 * 1024 * 1024; // 2MB

interface DocumentContent {
	document_id: number;
	title: string;
	document_type?: string;
	source_markdown: string;
	content_size_bytes?: number;
	chunk_count?: number;
	truncated?: boolean;
}

function DocumentSkeleton() {
	return (
		<div className="space-y-6 p-8 max-w-4xl mx-auto">
			<div className="h-8 w-3/4 rounded-md bg-muted/60 animate-pulse" />
			<div className="space-y-3">
				<div className="h-4 w-full rounded-md bg-muted/60 animate-pulse" />
				<div className="h-4 w-[95%] rounded-md bg-muted/60 animate-pulse [animation-delay:100ms]" />
				<div className="h-4 w-[88%] rounded-md bg-muted/60 animate-pulse [animation-delay:200ms]" />
				<div className="h-4 w-[60%] rounded-md bg-muted/60 animate-pulse [animation-delay:300ms]" />
			</div>
			<div className="h-6 w-2/5 rounded-md bg-muted/60 animate-pulse [animation-delay:400ms]" />
			<div className="space-y-3">
				<div className="h-4 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:500ms]" />
				<div className="h-4 w-[92%] rounded-md bg-muted/60 animate-pulse [animation-delay:600ms]" />
				<div className="h-4 w-[75%] rounded-md bg-muted/60 animate-pulse [animation-delay:700ms]" />
			</div>
		</div>
	);
}

interface DocumentTabContentProps {
	documentId: number;
	searchSpaceId: number;
	title?: string;
}

const EDITABLE_DOCUMENT_TYPES = new Set(["FILE", "NOTE"]);

export function DocumentTabContent({ documentId, searchSpaceId, title }: DocumentTabContentProps) {
	const [doc, setDoc] = useState<DocumentContent | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [isEditing, setIsEditing] = useState(false);
	const [saving, setSaving] = useState(false);
	const [downloading, setDownloading] = useState(false);
	const [editedMarkdown, setEditedMarkdown] = useState<string | null>(null);
	const markdownRef = useRef<string>("");
	const initialLoadDone = useRef(false);
	const changeCountRef = useRef(0);
	const router = useRouter();

	const isLargeDocument = (doc?.content_size_bytes ?? 0) > LARGE_DOCUMENT_THRESHOLD;

	useEffect(() => {
		const controller = new AbortController();
		setIsLoading(true);
		setError(null);
		setDoc(null);
		setIsEditing(false);
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
					setError("This document does not have viewable content.");
					setIsLoading(false);
					return;
				}

				markdownRef.current = data.source_markdown;
				setDoc(data);
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
	}, [documentId, searchSpaceId]);

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

			setDoc((prev) => (prev ? { ...prev, source_markdown: markdownRef.current } : prev));
			setEditedMarkdown(null);
			toast.success("Document saved! Reindexing in background...");
		} catch (err) {
			console.error("Error saving document:", err);
			toast.error(err instanceof Error ? err.message : "Failed to save document");
		} finally {
			setSaving(false);
		}
	}, [documentId, searchSpaceId]);

	if (isLoading) return <DocumentSkeleton />;

	if (error || !doc) {
		const isProcessing = error?.toLowerCase().includes("still being processed");
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
				<div className="rounded-full bg-muted/50 p-4">
					{isProcessing ? (
						<RefreshCw className="size-8 text-muted-foreground animate-spin" />
					) : (
						<FileQuestionMark className="size-8 text-muted-foreground" />
					)}
				</div>
				<div className="space-y-1.5 max-w-sm">
					<p className="font-semibold text-foreground text-lg">
						{isProcessing ? "Document is processing" : "Document unavailable"}
					</p>
					<p className="text-sm text-muted-foreground">{error || "An unknown error occurred"}</p>
				</div>
				{!isProcessing && (
					<Button
						variant="outline"
						size="sm"
						className="mt-1 gap-1.5"
						onClick={() => router.refresh()}
					>
						<RefreshCw className="size-3.5" />
						Retry
					</Button>
				)}
			</div>
		);
	}

	const isEditable = EDITABLE_DOCUMENT_TYPES.has(doc.document_type ?? "") && !isLargeDocument;

	if (isEditing && !isLargeDocument) {
		return (
			<div className="flex flex-col h-full overflow-hidden">
				<div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
					<div className="flex-1 min-w-0">
						<h1 className="text-base font-semibold truncate">{doc.title || title || "Untitled"}</h1>
						{editedMarkdown !== null && (
							<p className="text-xs text-muted-foreground">Unsaved changes</p>
						)}
					</div>
					<Button
						variant="outline"
						size="sm"
						onClick={() => {
							setIsEditing(false);
							setEditedMarkdown(null);
							changeCountRef.current = 0;
						}}
					>
						Done editing
					</Button>
				</div>
				<div className="flex-1 overflow-hidden">
					<PlateEditor
						key={`edit-${documentId}`}
						preset="full"
						markdown={doc.source_markdown}
						onMarkdownChange={handleMarkdownChange}
						readOnly={false}
						placeholder="Start writing..."
						editorVariant="default"
						onSave={handleSave}
						hasUnsavedChanges={editedMarkdown !== null}
						isSaving={saving}
						defaultEditing={true}
					/>
				</div>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-full overflow-hidden">
			<div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
				<h1 className="text-base font-semibold truncate flex-1 min-w-0">
					{doc.title || title || "Untitled"}
				</h1>
				{isEditable && (
					<Button
						variant="outline"
						size="sm"
						onClick={() => setIsEditing(true)}
						className="gap-1.5"
					>
						<PenLine className="size-3.5" />
						Edit
					</Button>
				)}
			</div>
			<div className="flex-1 overflow-auto">
				<div className="max-w-4xl mx-auto px-6 py-6">
					{isLargeDocument ? (
						<>
							<Alert className="mb-4">
								<FileText className="size-4" />
								<AlertDescription className="flex items-center justify-between gap-4">
									<span>
										This document is too large for the editor (
										{Math.round((doc.content_size_bytes ?? 0) / 1024 / 1024)}MB,{" "}
										{doc.chunk_count ?? 0} chunks). Showing a preview below.
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
												a.download = match?.[1] ?? `${doc.title || "document"}.md`;
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
							<MarkdownViewer content={doc.source_markdown} />
						</>
					) : (
						<MarkdownViewer content={doc.source_markdown} />
					)}
				</div>
			</div>
		</div>
	);
}
