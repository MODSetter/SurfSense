"use client";

import { AlertCircle, FileText, Loader2, Plus, X } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { BlockNoteEditor } from "@/components/DynamicBlockNoteEditor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { notesApiService } from "@/lib/apis/notes-api.service";

export default function NewNotePage() {
	const params = useParams();
	const router = useRouter();
	const searchSpaceId = Number(params.search_space_id);

	const [title, setTitle] = useState("");
	const [editorContent, setEditorContent] = useState<any>(null);
	const [creating, setCreating] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleCreate = async () => {
		if (!title.trim()) {
			toast.error("Please enter a title for your note");
			return;
		}

		setCreating(true);
		setError(null);

		try {
			const note = await notesApiService.createNote({
				search_space_id: searchSpaceId,
				title: title.trim(),
				blocknote_document: editorContent || undefined,
			});

			toast.success("Note created successfully!");
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

	const handleCancel = () => {
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
						<h1 className="text-lg font-semibold truncate">New Note</h1>
						<p className="text-xs text-muted-foreground">Create a new note</p>
					</div>
				</div>
				<Separator orientation="vertical" className="h-6" />
				<div className="flex items-center gap-2">
					<Button variant="outline" onClick={handleCancel} disabled={creating} className="gap-2">
						<X className="h-4 w-4" />
						Cancel
					</Button>
					<Button onClick={handleCreate} disabled={creating || !title.trim()} className="gap-2">
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

			{/* Content */}
			<div className="flex-1 overflow-hidden relative">
				<div className="h-full w-full overflow-auto p-6">
					<div className="max-w-4xl mx-auto space-y-6">
						{error && (
							<motion.div
								initial={{ opacity: 0, y: -10 }}
								animate={{ opacity: 1, y: 0 }}
							>
								<Card className="border-destructive/50">
									<CardHeader>
										<div className="flex items-center gap-2">
											<AlertCircle className="h-5 w-5 text-destructive" />
											<CardTitle className="text-destructive">Error</CardTitle>
										</div>
										<CardDescription>{error}</CardDescription>
									</CardHeader>
								</Card>
							</motion.div>
						)}

						<Card>
							<CardHeader>
								<CardTitle>Note Details</CardTitle>
								<CardDescription>Enter a title for your note</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label htmlFor="title">Title</Label>
									<Input
										id="title"
										placeholder="Enter note title..."
										value={title}
										onChange={(e) => setTitle(e.target.value)}
										disabled={creating}
										className="text-lg"
									/>
								</div>
							</CardContent>
						</Card>

						<Card>
							<CardHeader>
								<CardTitle>Content</CardTitle>
								<CardDescription>Start writing your note (optional)</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="min-h-[400px]">
									<BlockNoteEditor initialContent={undefined} onChange={setEditorContent} />
								</div>
							</CardContent>
						</Card>
					</div>
				</div>
			</div>
		</motion.div>
	);
}

