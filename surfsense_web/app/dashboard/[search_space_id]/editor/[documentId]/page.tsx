"use client";

import { useAtom } from "jotai";
import { AlertCircle, ArrowLeft, FileText } from "lucide-react";
import { motion } from "motion/react";
import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { hasUnsavedEditorChangesAtom, pendingEditorNavigationAtom } from "@/atoms/editor/ui.atoms";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { notesApiService } from "@/lib/apis/notes-api.service";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";

// Dynamically import PlateEditor (uses 'use client' internally)
const PlateEditor = dynamic(
	() => import("@/components/editor/plate-editor").then((mod) => ({ default: mod.PlateEditor })),
	{
		ssr: false,
		loading: () => (
			<div className="mx-auto w-full max-w-[900px] px-6 md:px-12 pt-10 space-y-4">
				<Skeleton className="h-8 w-3/5 rounded" />
				<div className="space-y-3 pt-4">
					<Skeleton className="h-4 w-full rounded" />
					<Skeleton className="h-4 w-full rounded" />
					<Skeleton className="h-4 w-4/5 rounded" />
				</div>
				<div className="space-y-3 pt-3">
					<Skeleton className="h-4 w-full rounded" />
					<Skeleton className="h-4 w-5/6 rounded" />
					<Skeleton className="h-4 w-3/4 rounded" />
				</div>
				<div className="space-y-3 pt-3">
					<Skeleton className="h-4 w-full rounded" />
					<Skeleton className="h-4 w-2/3 rounded" />
				</div>
			</div>
		),
	}
);

interface EditorContent {
	document_id: number;
	title: string;
	document_type?: string;
	source_markdown: string;
	updated_at: string | null;
}

/** Extract title from markdown: first # heading, or first non-empty line. */
function extractTitleFromMarkdown(markdown: string | null | undefined): string {
	if (!markdown) return "Untitled";
	for (const line of markdown.split("\n")) {
		const trimmed = line.trim();
		if (trimmed.startsWith("# ")) return trimmed.slice(2).trim() || "Untitled";
		if (trimmed) return trimmed.slice(0, 100);
	}
	return "Untitled";
}

export default function EditorPage() {
	const params = useParams();
	const router = useRouter();
	const documentId = params.documentId as string;
	const searchSpaceId = Number(params.search_space_id);
	const isNewNote = documentId === "new";

	const [document, setDocument] = useState<EditorContent | null>(null);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
	const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);

	// Store the latest markdown from the editor
	const markdownRef = useRef<string>("");
	const initialLoadDone = useRef(false);

	// Global state for cross-component communication
	const [, setGlobalHasUnsavedChanges] = useAtom(hasUnsavedEditorChangesAtom);
	const [pendingNavigation, setPendingNavigation] = useAtom(pendingEditorNavigationAtom);

	// Sync local unsaved changes state with global atom
	useEffect(() => {
		setGlobalHasUnsavedChanges(hasUnsavedChanges);
	}, [hasUnsavedChanges, setGlobalHasUnsavedChanges]);

	// Cleanup global state when component unmounts
	useEffect(() => {
		return () => {
			setGlobalHasUnsavedChanges(false);
			setPendingNavigation(null);
		};
	}, [setGlobalHasUnsavedChanges, setPendingNavigation]);

	// Handle pending navigation from sidebar
	useEffect(() => {
		if (pendingNavigation) {
			if (hasUnsavedChanges) {
				setShowUnsavedDialog(true);
			} else {
				router.push(pendingNavigation);
				setPendingNavigation(null);
			}
		}
	}, [pendingNavigation, hasUnsavedChanges, router, setPendingNavigation]);

	// Reset state when documentId changes
	useEffect(() => {
		setDocument(null);
		setError(null);
		setHasUnsavedChanges(false);
		setLoading(true);
		initialLoadDone.current = false;
	}, [documentId]);

	// Fetch document content
	useEffect(() => {
		async function fetchDocument() {
			if (isNewNote) {
				markdownRef.current = "";
				setDocument({
					document_id: 0,
					title: "Untitled",
					document_type: "NOTE",
					source_markdown: "",
					updated_at: null,
				});
				setLoading(false);
				initialLoadDone.current = true;
				return;
			}

			const token = getBearerToken();
			if (!token) {
				redirectToLogin();
				return;
			}

			try {
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${params.search_space_id}/documents/${documentId}/editor-content`,
					{ method: "GET" }
				);

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
					setLoading(false);
					return;
				}

				markdownRef.current = data.source_markdown;
				setDocument(data);
				setError(null);
				initialLoadDone.current = true;
			} catch (error) {
				console.error("Error fetching document:", error);
				setError(
					error instanceof Error ? error.message : "Failed to fetch document. Please try again."
				);
			} finally {
				setLoading(false);
			}
		}

		if (documentId) {
			fetchDocument();
		}
	}, [documentId, params.search_space_id, isNewNote]);

	const isNote = isNewNote || document?.document_type === "NOTE";

	// Extract title dynamically from current markdown for notes
	const displayTitle = useMemo(() => {
		if (isNote) {
			return extractTitleFromMarkdown(markdownRef.current || document?.source_markdown);
		}
		return document?.title || "Untitled";
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [isNote, document?.title, document?.source_markdown, hasUnsavedChanges]);

	// Handle markdown changes from the Plate editor
	const handleMarkdownChange = useCallback((md: string) => {
		markdownRef.current = md;
		if (initialLoadDone.current) {
			setHasUnsavedChanges(true);
		}
	}, []);

	// Save handler
	const handleSave = useCallback(async () => {
		const token = getBearerToken();
		if (!token) {
			toast.error("Please login to save");
			redirectToLogin();
			return;
		}

		setSaving(true);
		setError(null);

		try {
			const currentMarkdown = markdownRef.current;

			if (isNewNote) {
				const title = extractTitleFromMarkdown(currentMarkdown);

				// Create the note
				const note = await notesApiService.createNote({
					search_space_id: searchSpaceId,
					title,
					source_markdown: currentMarkdown || undefined,
				});

				// If there's content, save & trigger reindexing
				if (currentMarkdown) {
					const response = await authenticatedFetch(
						`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${note.id}/save`,
						{
							method: "POST",
							headers: { "Content-Type": "application/json" },
							body: JSON.stringify({ source_markdown: currentMarkdown }),
						}
					);

					if (!response.ok) {
						const errorData = await response
							.json()
							.catch(() => ({ detail: "Failed to save document" }));
						throw new Error(errorData.detail || "Failed to save document");
					}
				}

				setHasUnsavedChanges(false);
				toast.success("Note created successfully! Reindexing in background...");
				router.push(`/dashboard/${searchSpaceId}/documents`);
			} else {
				// Existing document — save
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${params.search_space_id}/documents/${documentId}/save`,
					{
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ source_markdown: currentMarkdown }),
					}
				);

				if (!response.ok) {
					const errorData = await response
						.json()
						.catch(() => ({ detail: "Failed to save document" }));
					throw new Error(errorData.detail || "Failed to save document");
				}

				setHasUnsavedChanges(false);
				toast.success("Document saved! Reindexing in background...");
				router.push(`/dashboard/${searchSpaceId}/documents`);
			}
		} catch (error) {
			console.error("Error saving document:", error);
			const errorMessage =
				error instanceof Error
					? error.message
					: isNewNote
						? "Failed to create note. Please try again."
						: "Failed to save document. Please try again.";
			setError(errorMessage);
			toast.error(errorMessage);
		} finally {
			setSaving(false);
		}
	}, [isNewNote, searchSpaceId, documentId, params.search_space_id, router]);

	const handleBack = () => {
		if (hasUnsavedChanges) {
			setShowUnsavedDialog(true);
		} else {
			router.push(`/dashboard/${searchSpaceId}/documents`);
		}
	};

	const handleConfirmLeave = () => {
		setShowUnsavedDialog(false);
		setGlobalHasUnsavedChanges(false);
		setHasUnsavedChanges(false);

		if (pendingNavigation) {
			router.push(pendingNavigation);
			setPendingNavigation(null);
		} else {
			router.push(`/dashboard/${searchSpaceId}/documents`);
		}
	};

	const handleSaveAndLeave = async () => {
		setShowUnsavedDialog(false);
		setPendingNavigation(null);
		await handleSave();
	};

	const handleCancelLeave = () => {
		setShowUnsavedDialog(false);
		setPendingNavigation(null);
	};

	if (loading) {
		return (
			<div className="flex flex-col h-screen w-full overflow-hidden">
				{/* Top bar skeleton — real back button & file icon, skeleton title */}
				<div className="flex h-14 md:h-16 shrink-0 items-center border-b bg-background pl-1.5 pr-3 md:pl-3 md:pr-6">
					<div className="flex items-center gap-1.5 md:gap-2 flex-1 min-w-0">
						<Button
							variant="ghost"
							size="icon"
							onClick={() => router.push(`/dashboard/${searchSpaceId}/documents`)}
							className="h-7 w-7 shrink-0 p-0"
						>
							<ArrowLeft className="h-4 w-4" />
							<span className="sr-only">Back</span>
						</Button>
						<FileText className="h-4 w-4 md:h-5 md:w-5 text-muted-foreground shrink-0" />
						<Skeleton className="h-5 w-40 rounded" />
					</div>
				</div>

				{/* Fixed toolbar placeholder — matches real toolbar styling */}
				<div className="sticky top-0 left-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 h-10" />

				{/* Content area skeleton — mimics document text lines */}
				<div className="flex-1 min-h-0 overflow-hidden">
					<div className="mx-auto w-full max-w-[900px] px-6 md:px-12 pt-10 space-y-4">
						{/* Title-like line */}
						<Skeleton className="h-8 w-3/5 rounded" />
						{/* Paragraph lines */}
						<div className="space-y-3 pt-4">
							<Skeleton className="h-4 w-full rounded" />
							<Skeleton className="h-4 w-full rounded" />
							<Skeleton className="h-4 w-4/5 rounded" />
						</div>
						<div className="space-y-3 pt-3">
							<Skeleton className="h-4 w-full rounded" />
							<Skeleton className="h-4 w-5/6 rounded" />
							<Skeleton className="h-4 w-3/4 rounded" />
						</div>
						<div className="space-y-3 pt-3">
							<Skeleton className="h-4 w-full rounded" />
							<Skeleton className="h-4 w-2/3 rounded" />
						</div>
					</div>
				</div>
			</div>
		);
	}

	if (error && !document) {
		return (
			<div className="flex items-center justify-center min-h-[400px] p-6">
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					className="w-full max-w-md"
				>
					<Card className="border-destructive/50">
						<CardHeader>
							<div className="flex items-center gap-2">
								<AlertCircle className="h-5 w-5 text-destructive" />
								<CardTitle className="text-destructive">Error</CardTitle>
							</div>
							<CardDescription>{error}</CardDescription>
						</CardHeader>
						<CardContent>
							<Button
								onClick={() => router.push(`/dashboard/${searchSpaceId}/documents`)}
								variant="outline"
								className="gap-2"
							>
								<ArrowLeft className="h-4 w-4" />
								Back
							</Button>
						</CardContent>
					</Card>
				</motion.div>
			</div>
		);
	}

	if (!document && !isNewNote) {
		return (
			<div className="flex items-center justify-center min-h-[400px] p-6">
				<Card className="w-full max-w-md">
					<CardContent className="flex flex-col items-center justify-center py-12">
						<FileText className="h-12 w-12 text-muted-foreground mb-4" />
						<p className="text-muted-foreground">Document not found</p>
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			className="flex flex-col h-screen w-full overflow-hidden"
		>
			{/* Toolbar */}
			<div className="flex h-14 md:h-16 shrink-0 items-center border-b bg-background pl-1.5 pr-3 md:pl-3 md:pr-6">
				<div className="flex items-center gap-1.5 md:gap-2 flex-1 min-w-0">
					<Button
						variant="ghost"
						size="icon"
						onClick={handleBack}
						disabled={saving}
						className="h-7 w-7 shrink-0 p-0"
					>
						<ArrowLeft className="h-4 w-4" />
						<span className="sr-only">Back</span>
					</Button>
					<FileText className="h-4 w-4 md:h-5 md:w-5 text-muted-foreground shrink-0" />
					<div className="flex flex-col min-w-0">
						<h1 className="text-base md:text-lg font-semibold truncate">{displayTitle}</h1>
						{hasUnsavedChanges && (
							<p className="text-[10px] md:text-xs text-muted-foreground">Unsaved changes</p>
						)}
					</div>
				</div>
			</div>

			{/* Editor Container */}
			<div className="flex-1 min-h-0 flex flex-col overflow-hidden relative">
				{error && (
					<motion.div
						initial={{ opacity: 0, y: -10 }}
						animate={{ opacity: 1, y: 0 }}
						className="px-3 md:px-6 pt-3 md:pt-6"
					>
						<div className="flex items-center gap-2 p-4 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive max-w-4xl mx-auto">
							<AlertCircle className="h-5 w-5 shrink-0" />
							<p className="text-sm">{error}</p>
						</div>
					</motion.div>
				)}
				<div className="flex-1 min-h-0">
					<PlateEditor
						key={documentId}
						preset="full"
						markdown={document?.source_markdown ?? ""}
						onMarkdownChange={handleMarkdownChange}
						onSave={handleSave}
						hasUnsavedChanges={hasUnsavedChanges}
						isSaving={saving}
						defaultEditing={true}
					/>
				</div>
			</div>

			{/* Unsaved Changes Dialog */}
			<AlertDialog
				open={showUnsavedDialog}
				onOpenChange={(open) => {
					if (!open) handleCancelLeave();
				}}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
						<AlertDialogDescription>
							You have unsaved changes. Are you sure you want to leave?
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel onClick={handleCancelLeave}>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleSaveAndLeave}>Save</AlertDialogAction>
						<AlertDialogAction
							onClick={handleConfirmLeave}
							className="border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground"
						>
							Leave without saving
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</motion.div>
	);
}
