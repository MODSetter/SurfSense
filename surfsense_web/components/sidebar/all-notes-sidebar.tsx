"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, MoreHorizontal, Plus, Search, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { notesApiService } from "@/lib/apis/notes-api.service";
import { cn } from "@/lib/utils";

interface AllNotesSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: string;
	onAddNote?: () => void;
}

export function AllNotesSidebar({
	open,
	onOpenChange,
	searchSpaceId,
	onAddNote,
}: AllNotesSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const queryClient = useQueryClient();
	const [deletingNoteId, setDeletingNoteId] = useState<number | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	// Fetch all notes (when no search query)
	const {
		data: notesData,
		error: notesError,
		isLoading: isLoadingNotes,
	} = useQuery({
		queryKey: ["all-notes", searchSpaceId],
		queryFn: () =>
			notesApiService.getNotes({
				search_space_id: Number(searchSpaceId),
				page_size: 1000,
			}),
		enabled: !!searchSpaceId && open && !debouncedSearchQuery,
	});

	// Search notes (when there's a search query)
	const {
		data: searchData,
		error: searchError,
		isLoading: isSearching,
	} = useQuery({
		queryKey: ["search-notes", searchSpaceId, debouncedSearchQuery],
		queryFn: () =>
			documentsApiService.searchDocuments({
				queryParams: {
					search_space_id: Number(searchSpaceId),
					document_types: ["NOTE"],
					title: debouncedSearchQuery,
					page_size: 100,
				},
			}),
		enabled: !!searchSpaceId && open && !!debouncedSearchQuery,
	});

	// Handle note navigation
	const handleNoteClick = useCallback(
		(noteId: number, noteSearchSpaceId: number) => {
			router.push(`/dashboard/${noteSearchSpaceId}/editor/${noteId}`);
			onOpenChange(false);
		},
		[router, onOpenChange]
	);

	// Handle note deletion
	const handleDeleteNote = useCallback(
		async (noteId: number, noteSearchSpaceId: number) => {
			setDeletingNoteId(noteId);
			try {
				await notesApiService.deleteNote({
					search_space_id: noteSearchSpaceId,
					note_id: noteId,
				});
				// Invalidate queries to refresh the list
				queryClient.invalidateQueries({ queryKey: ["all-notes", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["notes", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["search-notes", searchSpaceId] });
			} catch (error) {
				console.error("Error deleting note:", error);
			} finally {
				setDeletingNoteId(null);
			}
		},
		[queryClient, searchSpaceId]
	);

	// Clear search
	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	// Determine which data to show
	const isSearchMode = !!debouncedSearchQuery;
	const isLoading = isSearchMode ? isSearching : isLoadingNotes;
	const error = isSearchMode ? searchError : notesError;

	// Transform notes data - handle both regular notes and search results
	const notes = useMemo(() => {
		if (isSearchMode && searchData?.items) {
			return searchData.items.map((doc) => ({
				id: doc.id,
				title: doc.title,
				search_space_id: doc.search_space_id,
			}));
		}
		return notesData?.items ?? [];
	}, [isSearchMode, searchData, notesData]);

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="left" className="w-80 p-0 flex flex-col">
				<SheetHeader className="px-4 py-4 border-b space-y-3">
					<SheetTitle>{t("all_notes") || "All Notes"}</SheetTitle>
					<SheetDescription className="sr-only">
						{t("all_notes_description") || "Browse and manage all your notes"}
					</SheetDescription>

					{/* Search Input */}
					<div className="relative">
						<Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
						<Input
							type="text"
							placeholder={t("search_notes") || "Search notes..."}
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							className="pl-9 pr-8 h-9"
						/>
						{searchQuery && (
							<Button
								variant="ghost"
								size="icon"
								className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
								onClick={handleClearSearch}
							>
								<X className="h-3.5 w-3.5" />
								<span className="sr-only">Clear search</span>
							</Button>
						)}
					</div>
				</SheetHeader>

				<ScrollArea className="flex-1">
					<div className="p-2">
						{isLoading ? (
							<div className="flex items-center justify-center py-8">
								<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
							</div>
						) : error ? (
							<div className="text-center py-8 text-sm text-destructive">
								{t("error_loading_notes") || "Error loading notes"}
							</div>
						) : notes.length > 0 ? (
							<div className="space-y-1">
								{notes.map((note) => {
									const isDeleting = deletingNoteId === note.id;

									return (
										<div
											key={note.id}
											className={cn(
												"group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
												"hover:bg-accent hover:text-accent-foreground",
												"transition-colors cursor-pointer",
												isDeleting && "opacity-50 pointer-events-none"
											)}
										>
											{/* Main clickable area for navigation */}
											<button
												type="button"
												onClick={() => handleNoteClick(note.id, note.search_space_id)}
												disabled={isDeleting}
												className="flex items-center gap-2 flex-1 min-w-0 text-left"
											>
												<FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
												<span className="truncate">{note.title}</span>
											</button>

											{/* Actions dropdown - separate from main click area */}
											<DropdownMenu>
												<DropdownMenuTrigger asChild>
													<Button
														variant="ghost"
														size="icon"
														className={cn(
															"h-6 w-6 shrink-0",
															"opacity-0 group-hover:opacity-100 focus:opacity-100",
															"transition-opacity"
														)}
														disabled={isDeleting}
													>
														{isDeleting ? (
															<Loader2 className="h-3.5 w-3.5 animate-spin" />
														) : (
															<MoreHorizontal className="h-3.5 w-3.5" />
														)}
														<span className="sr-only">More options</span>
													</Button>
												</DropdownMenuTrigger>
												<DropdownMenuContent align="end" className="w-40">
													<DropdownMenuItem
														onClick={() => handleDeleteNote(note.id, note.search_space_id)}
														className="text-destructive focus:text-destructive"
													>
														<Trash2 className="mr-2 h-4 w-4" />
														<span>Delete</span>
													</DropdownMenuItem>
												</DropdownMenuContent>
											</DropdownMenu>
										</div>
									);
								})}
							</div>
						) : isSearchMode ? (
							<div className="text-center py-8">
								<Search className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
								<p className="text-sm text-muted-foreground">
									{t("no_results_found") || "No notes found"}
								</p>
								<p className="text-xs text-muted-foreground/70 mt-1">
									{t("try_different_search") || "Try a different search term"}
								</p>
							</div>
						) : (
							<div className="text-center py-8">
								<FileText className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
								<p className="text-sm text-muted-foreground mb-4">
									{t("no_notes") || "No notes yet"}
								</p>
								{onAddNote && (
									<Button
										variant="outline"
										size="sm"
										onClick={() => {
											onAddNote();
											onOpenChange(false);
										}}
									>
										<Plus className="mr-2 h-4 w-4" />
										{t("create_new_note") || "Create a note"}
									</Button>
								)}
							</div>
						)}
					</div>
				</ScrollArea>

				{/* Footer with Add Note button */}
				{onAddNote && notes.length > 0 && (
					<div className="p-3 border-t">
						<Button
							onClick={() => {
								onAddNote();
								onOpenChange(false);
							}}
							className="w-full"
							size="sm"
						>
							<Plus className="mr-2 h-4 w-4" />
							{t("create_new_note") || "Create a new note"}
						</Button>
					</div>
				)}
			</SheetContent>
		</Sheet>
	);
}
