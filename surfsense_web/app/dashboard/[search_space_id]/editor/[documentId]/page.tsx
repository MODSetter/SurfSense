"use client";

import { AlertCircle, FileText, Loader2, Save, X } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BlockNoteEditor } from "@/components/DynamicBlockNoteEditor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface EditorContent {
	document_id: number;
	title: string;
	blocknote_document: any;
	last_edited_at: string | null;
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

	// Get auth token
	const token =
		typeof window !== "undefined" ? localStorage.getItem("surfsense_bearer_token") : null;

	// Fetch document content - DIRECT CALL TO FASTAPI
	useEffect(() => {
		async function fetchDocument() {
			if (!token) {
				console.error("No auth token found");
				setError("Please login to access the editor");
				setLoading(false);
				return;
			}

			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}/editor-content`,
					{
						headers: {
							Authorization: `Bearer ${token}`,
						},
					}
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

		if (documentId && token) {
			fetchDocument();
		}
	}, [documentId, token]);

	// Track changes to mark as unsaved
	useEffect(() => {
		if (editorContent && document) {
			setHasUnsavedChanges(true);
		}
	}, [editorContent, document]);

	// Auto-save every 30 seconds - DIRECT CALL TO FASTAPI
	useEffect(() => {
		if (!editorContent || !token || !hasUnsavedChanges) return;

		const interval = setInterval(async () => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}/blocknote-content`,
					{
						method: "PUT",
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${token}`,
						},
						body: JSON.stringify({ blocknote_document: editorContent }),
					}
				);

				if (response.ok) {
					setHasUnsavedChanges(false);
					toast.success("Auto-saved", { duration: 2000 });
				}
			} catch (error) {
				console.error("Auto-save failed:", error);
			}
		}, 30000); // 30 seconds

		return () => clearInterval(interval);
	}, [editorContent, documentId, token, hasUnsavedChanges]);

	// Save and exit - DIRECT CALL TO FASTAPI
	const handleSave = async () => {
		if (!token) {
			toast.error("Please login to save");
			return;
		}

		if (!editorContent) {
			toast.error("No content to save");
			return;
		}

		setSaving(true);
		try {
			// Save blocknote_document to database (without finalizing/reindexing)
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}/blocknote-content`,
				{
					method: "PUT",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
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
			toast.success("Document saved successfully");

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

	const handleCancel = () => {
		if (hasUnsavedChanges) {
			if (confirm("You have unsaved changes. Are you sure you want to leave?")) {
				router.back();
			}
		} else {
			router.back();
		}
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
						<h1 className="text-lg font-semibold truncate">{document.title}</h1>
						{hasUnsavedChanges && <p className="text-xs text-muted-foreground">Unsaved changes</p>}
					</div>
				</div>
				<Separator orientation="vertical" className="h-6" />
				<div className="flex items-center gap-2">
					<Button variant="outline" onClick={handleCancel} disabled={saving} className="gap-2">
						<X className="h-4 w-4" />
						Cancel
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
						<BlockNoteEditor initialContent={editorContent} onChange={setEditorContent} />
					</div>
				</div>
			</div>
		</motion.div>
	);
}
