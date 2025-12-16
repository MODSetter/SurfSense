"use client";

import { AlertCircle, ArrowLeft, FileText, Loader2, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { BlockNoteEditor } from "@/components/DynamicBlockNoteEditor";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { notesApiService } from "@/lib/apis/notes-api.service";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";

// Helper function to extract title from BlockNote document
// Takes the text content from the first block (should be a heading)
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

export default function NewNotePage() {
	const params = useParams();
	const router = useRouter();
	const searchSpaceId = Number(params.search_space_id);

	const [editorContent, setEditorContent] = useState<any>(null);
	const [creating, setCreating] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Extract title dynamically from editor content
	const dynamicTitle = useMemo(() => {
		return extractTitleFromBlockNote(editorContent);
	}, [editorContent]);

	const handleCreate = async () => {
		setCreating(true);
		setError(null);

		try {
			// Extract title from first block of editor content
			const title = extractTitleFromBlockNote(editorContent);

			// Create the note first
			const note = await notesApiService.createNote({
				search_space_id: searchSpaceId,
				title: title,
				blocknote_document: editorContent || undefined,
			});

			// If there's content, save it properly and trigger reindexing
			if (editorContent) {
				const token = getBearerToken();
				if (!token) {
					toast.error("Please login to save");
					redirectToLogin();
					return;
				}

				// Call the save endpoint to properly save blocknote_document and trigger reindexing
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

			toast.success("Note created successfully! Reindexing in background...");
			// Redirect to editor
			router.push(`/dashboard/${searchSpaceId}/editor/${note.id}`);
		} catch (error) {
			console.error("Error creating note:", error);
			const errorMessage =
				error instanceof Error ? error.message : "Failed to create note. Please try again.";
			setError(errorMessage);
			toast.error(errorMessage);
		} finally {
			setCreating(false);
		}
	};

	const handleBack = () => {
		router.back();
	};

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
						<h1 className="text-lg font-semibold truncate">{dynamicTitle}</h1>
					</div>
				</div>
				<Separator orientation="vertical" className="h-6" />
				<div className="flex items-center gap-2">
					<Button variant="outline" onClick={handleBack} disabled={creating} className="gap-2">
						<ArrowLeft className="h-4 w-4" />
						Back
					</Button>
					<Button onClick={handleCreate} disabled={creating} className="gap-2">
						{creating ? (
							<>
								<Loader2 className="h-4 w-4 animate-spin" />
								Creating...
							</>
						) : (
							<>
								<Plus className="h-4 w-4" />
								Create Note
							</>
						)}
					</Button>
				</div>
			</div>

			{/* Editor Container - matches editor page layout */}
			<div className="flex-1 overflow-hidden relative">
				<div className="h-full w-full overflow-auto p-6">
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
						<BlockNoteEditor initialContent={undefined} onChange={setEditorContent} useTitleBlock={true} />
					</div>
				</div>
			</div>
		</motion.div>
	);
}