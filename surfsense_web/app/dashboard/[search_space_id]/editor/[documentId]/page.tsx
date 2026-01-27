"use client";

import { useAtom } from "jotai";
import { AlertCircle, ArrowLeft, FileText, Save } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { hasUnsavedEditorChangesAtom, pendingEditorNavigationAtom } from "@/atoms/editor/ui.atoms";
import { BlockNoteEditor } from "@/components/DynamicBlockNoteEditor";
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
import { Spinner } from "@/components/ui/spinner";
import { notesApiService } from "@/lib/apis/notes-api.service";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";

// BlockNote types
type BlockNoteInlineContent =
	| string
	| { text?: string; type?: string; styles?: Record<string, unknown> };

interface BlockNoteBlock {
	type: string;
	content?: BlockNoteInlineContent[];
	children?: BlockNoteBlock[];
	props?: Record<string, unknown>;
}

type BlockNoteDocument = BlockNoteBlock[] | null | undefined;

interface EditorContent {
	document_id: number;
	title: string;
	document_type?: string;
	blocknote_document: BlockNoteDocument;
	updated_at: string | null;
}

// Helper function to extract title from BlockNote document
// Takes the text content from the first block (should be a heading for notes)
function extractTitleFromBlockNote(blocknoteDocument: BlockNoteDocument): string {
	if (!blocknoteDocument || !Array.isArray(blocknoteDocument) || blocknoteDocument.length === 0) {
		return "Untitled";
	}

	const firstBlock = blocknoteDocument[0];
	if (!firstBlock) {
		return "Untitled";
	}

	// Extract text from block content
	// BlockNote blocks have a content array with inline content
	if (firstBlock.content && Array.isArray(firstBlock.content)) {
		const textContent = firstBlock.content
			.map((item: BlockNoteInlineContent) => {
				if (typeof item === "string") return item;
				if (typeof item === "object" && item?.text) return item.text;
				return "";
			})
			.join("")
			.trim();
		return textContent || "Untitled";
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
	const [editorContent, setEditorContent] = useState<BlockNoteDocument>(null);
	const [error, setError] = useState<string | null>(null);
	const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
	const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);

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

	// Handle pending navigation from sidebar (e.g., when user clicks "+" to create new note)
	useEffect(() => {
		if (pendingNavigation) {
			if (hasUnsavedChanges) {
				// Show dialog to confirm navigation
				setShowUnsavedDialog(true);
			} else {
				// No unsaved changes, navigate immediately
				router.push(pendingNavigation);
				setPendingNavigation(null);
			}
		}
	}, [pendingNavigation, hasUnsavedChanges, router, setPendingNavigation]);

	// Reset state when documentId changes (e.g., navigating from existing note to new note)
	useEffect(() => {
		setDocument(null);
		setEditorContent(null);
		setError(null);
		setHasUnsavedChanges(false);
		setLoading(true);
	}, []);

	// Fetch document content - DIRECT CALL TO FASTAPI
	// Skip fetching if this is a new note
	useEffect(() => {
		async function fetchDocument() {
			// For new notes, initialize with empty state
			if (isNewNote) {
				setDocument({
					document_id: 0,
					title: "Untitled",
					document_type: "NOTE",
					blocknote_document: null,
					updated_at: null,
				});
				setEditorContent(null);
				setLoading(false);
				return;
			}

			const token = getBearerToken();
			if (!token) {
				console.error("No auth token found");
				// Redirect to login with current path saved
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
					const errorMessage = errorData.detail || "Failed to fetch document";
					throw new Error(errorMessage);
				}

				const data = await response.json();

				// Check if blocknote_document exists
				if (!data.blocknote_document) {
					const errorMsg =
						"This document does not have BlockNote content. Please re-upload the document to enable editing.";
					setError(errorMsg);
					setLoading(false);
					return;
				}

				setDocument(data);
				setEditorContent(data.blocknote_document);
				setError(null);
			} catch (error) {
				console.error("Error fetching document:", error);
				const errorMessage =
					error instanceof Error ? error.message : "Failed to fetch document. Please try again.";
				setError(errorMessage);
			} finally {
				setLoading(false);
			}
		}

		if (documentId) {
			fetchDocument();
		}
	}, [documentId, params.search_space_id, isNewNote]);

	// Track changes to mark as unsaved
	useEffect(() => {
		if (editorContent && document) {
			setHasUnsavedChanges(true);
		}
	}, [editorContent, document]);

	// Check if this is a NOTE type document
	const isNote = isNewNote || document?.document_type === "NOTE";

	// Extract title dynamically from editor content for notes, otherwise use document title
	const displayTitle = useMemo(() => {
		if (isNote && editorContent) {
			return extractTitleFromBlockNote(editorContent);
		}
		return document?.title || "Untitled";
	}, [isNote, editorContent, document?.title]);

	// TODO: Maybe add Auto-save every 30 seconds - DIRECT CALL TO FASTAPI

	// Save and exit - DIRECT CALL TO FASTAPI
	// For new notes, create the note first, then save
	const handleSave = async () => {
		const token = getBearerToken();
		if (!token) {
			toast.error("Please login to save");
			redirectToLogin();
			return;
		}

		setSaving(true);
		setError(null);

		try {
			// If this is a new note, create it first
			if (isNewNote) {
				const title = extractTitleFromBlockNote(editorContent);

				// Create the note first
				const note = await notesApiService.createNote({
					search_space_id: searchSpaceId,
					title: title,
					blocknote_document: editorContent || undefined,
				});

				// If there's content, save it properly and trigger reindexing
				if (editorContent) {
					const response = await authenticatedFetch(
						`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${note.id}/save`,
						{
							method: "POST",
							headers: { "Content-Type": "application/json" },
							body: JSON.stringify({ blocknote_document: editorContent }),
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

				// Redirect to documents page after successful save
				router.push(`/dashboard/${searchSpaceId}/documents`);
			} else {
				// Existing document - save normally
				if (!editorContent) {
					toast.error("No content to save");
					setSaving(false);
					return;
				}

				// Save blocknote_document and trigger reindexing in background
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${params.search_space_id}/documents/${documentId}/save`,
					{
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ blocknote_document: editorContent }),
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

				// Redirect to documents page after successful save
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
	};

	const handleBack = () => {
		if (hasUnsavedChanges) {
			setShowUnsavedDialog(true);
		} else {
			router.push(`/dashboard/${searchSpaceId}/documents`);
		}
	};

	const handleConfirmLeave = () => {
		setShowUnsavedDialog(false);
		// Clear global unsaved state
		setGlobalHasUnsavedChanges(false);
		setHasUnsavedChanges(false);

		// If there's a pending navigation (from sidebar), use that; otherwise go back to documents
		if (pendingNavigation) {
			router.push(pendingNavigation);
			setPendingNavigation(null);
		} else {
			router.push(`/dashboard/${searchSpaceId}/documents`);
		}
	};

	const handleCancelLeave = () => {
		setShowUnsavedDialog(false);
		// Clear pending navigation if user cancels
		setPendingNavigation(null);
	};

	if (loading) {
		return (
			<div className="flex items-center justify-center min-h-[400px] p-6">
				<Card className="w-full max-w-md">
					<CardContent className="flex flex-col items-center justify-center py-12">
						<Spinner size="xl" className="text-primary mb-4" />
						<p className="text-muted-foreground">Loading editor</p>
					</CardContent>
				</Card>
			</div>
		);
	}

	if (error) {
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
			className="flex flex-col min-h-screen w-full"
		>
			{/* Toolbar */}
			<div className="sticky top-0 z-40 flex h-14 md:h-16 shrink-0 items-center gap-2 md:gap-4 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 px-3 md:px-6">
				<div className="flex items-center gap-2 md:gap-3 flex-1 min-w-0">
					<FileText className="h-4 w-4 md:h-5 md:w-5 text-muted-foreground shrink-0" />
					<div className="flex flex-col min-w-0">
						<h1 className="text-base md:text-lg font-semibold truncate">{displayTitle}</h1>
						{hasUnsavedChanges && (
							<p className="text-[10px] md:text-xs text-muted-foreground">Unsaved changes</p>
						)}
					</div>
				</div>

				<div className="flex items-center gap-2">
					<Button
						variant="outline"
						onClick={handleBack}
						disabled={saving}
						className="gap-1 md:gap-2 px-2 md:px-4 h-8 md:h-10"
					>
						<ArrowLeft className="h-3.5 w-3.5 md:h-4 md:w-4" />
						<span className="text-xs md:text-sm">Back</span>
					</Button>
					<Button
						onClick={handleSave}
						disabled={saving}
						className="gap-1 md:gap-2 px-2 md:px-4 h-8 md:h-10"
					>
						{saving ? (
							<>
								<Spinner size="sm" className="h-3.5 w-3.5 md:h-4 md:w-4" />
								<span className="text-xs md:text-sm">{isNewNote ? "Creating" : "Saving"}</span>
							</>
						) : (
							<>
								<Save className="h-3.5 w-3.5 md:h-4 md:w-4" />
								<span className="text-xs md:text-sm">Save</span>
							</>
						)}
					</Button>
				</div>
			</div>

			{/* Editor Container */}
			<div className="flex-1 min-h-0 overflow-hidden relative">
				<div className="h-full w-full overflow-auto p-3 md:p-6">
					{error && (
						<motion.div
							initial={{ opacity: 0, y: -10 }}
							animate={{ opacity: 1, y: 0 }}
							className="mb-6 max-w-4xl mx-auto"
						>
							<div className="flex items-center gap-2 p-4 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive">
								<AlertCircle className="h-5 w-5 shrink-0" />
								<p className="text-sm">{error}</p>
							</div>
						</motion.div>
					)}
					<div className="max-w-4xl mx-auto">
						<BlockNoteEditor
							key={documentId} // Force re-mount when document changes
							initialContent={isNewNote ? undefined : editorContent}
							onChange={setEditorContent}
							useTitleBlock={isNote}
						/>
					</div>
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
						<AlertDialogAction onClick={handleConfirmLeave}>OK</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</motion.div>
	);
}
