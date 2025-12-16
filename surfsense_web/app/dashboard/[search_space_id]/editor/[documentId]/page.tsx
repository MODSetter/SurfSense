"use client";

import { AlertCircle, ArrowLeft, FileText, Loader2, Save, X } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
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
import { Separator } from "@/components/ui/separator";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";

interface EditorContent {
	document_id: number;
	title: string;
	document_type?: string;
	blocknote_document: any;
	updated_at: string | null;
}

// Helper function to extract title from BlockNote document
// Takes the text content from the first block (should be a heading for notes)
function extractTitleFromBlockNote(blocknoteDocument: any[] | null | undefined): string {
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
			.map((item: any) => {
				if (typeof item === "string") return item;
				if (item?.text) return item.text;
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

	const [document, setDocument] = useState<EditorContent | null>(null);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [editorContent, setEditorContent] = useState<any>(null);
	const [error, setError] = useState<string | null>(null);
	const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
	const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);

	// Fetch document content - DIRECT CALL TO FASTAPI
	useEffect(() => {
		async function fetchDocument() {
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
					throw new Error(errorData.detail || "Failed to fetch document");
				}

				const data = await response.json();

				// Check if blocknote_document exists
				if (!data.blocknote_document) {
					setError(
						"This document does not have BlockNote content. Please re-upload the document to enable editing."
					);
					setLoading(false);
					return;
				}

				setDocument(data);
				setEditorContent(data.blocknote_document);
				setError(null);
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
	}, [documentId, params.search_space_id]);

	// Track changes to mark as unsaved
	useEffect(() => {
		if (editorContent && document) {
			setHasUnsavedChanges(true);
		}
	}, [editorContent, document]);

	// Check if this is a NOTE type document
	const isNote = document?.document_type === "NOTE";

	// Extract title dynamically from editor content for notes, otherwise use document title
	const displayTitle = useMemo(() => {
		if (isNote && editorContent) {
			return extractTitleFromBlockNote(editorContent);
		}
		return document?.title || "Untitled";
	}, [isNote, editorContent, document?.title]);

	// TODO: Maybe add Auto-save every 30 seconds - DIRECT CALL TO FASTAPI

	// Save and exit - DIRECT CALL TO FASTAPI
	const handleSave = async () => {
		const token = getBearerToken();
		if (!token) {
			toast.error("Please login to save");
			redirectToLogin();
			return;
		}

		if (!editorContent) {
			toast.error("No content to save");
			return;
		}

		setSaving(true);
		try {
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

			// Small delay before redirect to show success message
			setTimeout(() => {
				router.push(`/dashboard/${params.search_space_id}/documents`);
			}, 500);
		} catch (error) {
			console.error("Error saving document:", error);
			toast.error(
				error instanceof Error ? error.message : "Failed to save document. Please try again."
			);
		} finally {
			setSaving(false);
		}
	};

	const handleBack = () => {
		if (hasUnsavedChanges) {
			setShowUnsavedDialog(true);
		} else {
			router.back();
		}
	};

	const handleConfirmLeave = () => {
		setShowUnsavedDialog(false);
		router.back();
	};

	if (loading) {
		return (
			<div className="flex items-center justify-center min-h-[400px] p-6">
				<Card className="w-full max-w-md">
					<CardContent className="flex flex-col items-center justify-center py-12">
						<Loader2 className="h-12 w-12 text-primary animate-spin mb-4" />
						<p className="text-muted-foreground">Loading editor...</p>
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
							<Button onClick={() => router.back()} variant="outline" className="w-full">
								<X className="mr-2 h-4 w-4" />
								Go Back
							</Button>
						</CardContent>
					</Card>
				</motion.div>
			</div>
		);
	}

	if (!document) {
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
			className="flex flex-col h-full w-full"
		>
			{/* Toolbar */}
			<div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-4 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 px-6">
				<div className="flex items-center gap-3 flex-1 min-w-0">
					<FileText className="h-5 w-5 text-muted-foreground shrink-0" />
					<div className="flex flex-col min-w-0">
						<h1 className="text-lg font-semibold truncate">{displayTitle}</h1>
						{hasUnsavedChanges && <p className="text-xs text-muted-foreground">Unsaved changes</p>}
					</div>
				</div>
				<Separator orientation="vertical" className="h-6" />
				<div className="flex items-center gap-2">
					<Button variant="outline" onClick={handleBack} disabled={saving} className="gap-2">
						<ArrowLeft className="h-4 w-4" />
						Back
					</Button>
					<Button onClick={handleSave} disabled={saving} className="gap-2">
						{saving ? (
							<>
								<Loader2 className="h-4 w-4 animate-spin" />
								Saving...
							</>
						) : (
							<>
								<Save className="h-4 w-4" />
								Save & Exit
							</>
						)}
					</Button>
				</div>
			</div>

			{/* Editor Container */}
			<div className="flex-1 overflow-hidden relative">
				<div className="h-full w-full overflow-auto p-6">
					<div className="max-w-4xl mx-auto">
						<BlockNoteEditor
							initialContent={editorContent}
							onChange={setEditorContent}
							useTitleBlock={isNote}
						/>
					</div>
				</div>
			</div>

			{/* Unsaved Changes Dialog */}
			<AlertDialog open={showUnsavedDialog} onOpenChange={setShowUnsavedDialog}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
						<AlertDialogDescription>
							You have unsaved changes. Are you sure you want to leave?
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleConfirmLeave}>OK</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</motion.div>
	);
}
