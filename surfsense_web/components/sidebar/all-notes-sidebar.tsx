"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { FileText, Loader2, MoreHorizontal, Plus, Search, Trash2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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
	const [mounted, setMounted] = useState(false);
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	// Handle mounting for portal
	useEffect(() => {
		setMounted(true);
	}, []);

	// Handle escape key
	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) {
				onOpenChange(false);
			}
		};
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

	// Lock body scroll when open
	useEffect(() => {
		if (open) {
			document.body.style.overflow = "hidden";
		} else {
			document.body.style.overflow = "";
		}
		return () => {
			document.body.style.overflow = "";
		};
	}, [open]);

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

	// Transform and sort notes data - handle both regular notes and search results
	const notes = useMemo(() => {
		let notesList: {
			id: number;
			title: string;
			search_space_id: number;
			created_at: string;
			updated_at?: string | null;
		}[];

		if (isSearchMode && searchData?.items) {
			notesList = searchData.items.map((doc) => ({
				id: doc.id,
				title: doc.title,
				search_space_id: doc.search_space_id,
				created_at: doc.created_at,
				updated_at: doc.updated_at,
			}));
		} else {
			notesList = notesData?.items ?? [];
		}

		// Sort notes by updated_at (most recent first), fallback to created_at
		return [...notesList].sort((a, b) => {
			const dateA = a.updated_at
				? new Date(a.updated_at).getTime()
				: new Date(a.created_at).getTime();
			const dateB = b.updated_at
				? new Date(b.updated_at).getTime()
				: new Date(b.created_at).getTime();
			return dateB - dateA; // Descending order (most recent first)
		});
	}, [isSearchMode, searchData, notesData]);

	if (!mounted) return null;

	return createPortal(
		<AnimatePresence>
			{open && (
				<>
					{/* Backdrop */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="fixed inset-0 z-50 bg-black/50"
						onClick={() => onOpenChange(false)}
						aria-hidden="true"
					/>

					{/* Panel */}
					<motion.div
						initial={{ x: "-100%" }}
						animate={{ x: 0 }}
						exit={{ x: "-100%" }}
						transition={{ type: "spring", damping: 25, stiffness: 300 }}
						className="fixed inset-y-0 left-0 z-50 w-80 bg-background shadow-xl flex flex-col"
						role="dialog"
						aria-modal="true"
						aria-label={t("all_notes") || "All Notes"}
					>
						{/* Header */}
						<div className="flex-shrink-0 p-4 pb-3 space-y-3">
							<div className="flex items-center justify-between">
								<h2 className="text-lg font-semibold">{t("all_notes") || "All Notes"}</h2>
								<Button
									variant="ghost"
									size="icon"
									className="h-8 w-8 rounded-full"
									onClick={() => onOpenChange(false)}
								>
									<X className="h-4 w-4" />
									<span className="sr-only">Close</span>
								</Button>
							</div>

							{/* Search Input */}
							<div className="relative">
								<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
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
										<span className="sr-only">{t("clear_search") || "Clear search"}</span>
									</Button>
								)}
							</div>
						</div>

						{/* Scrollable Content */}
						<div className="flex-1 overflow-y-auto overflow-x-hidden p-2">
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
												<Tooltip>
													<TooltipTrigger asChild>
														<button
															type="button"
															onClick={() => handleNoteClick(note.id, note.search_space_id)}
															disabled={isDeleting}
															className="flex items-center gap-2 flex-1 min-w-0 text-left overflow-hidden"
														>
															<FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
															<span className="truncate">{note.title}</span>
														</button>
													</TooltipTrigger>
													<TooltipContent side="bottom" align="start">
														<div className="space-y-1">
															<p>
																{t("created") || "Created"}:{" "}
																{format(new Date(note.created_at), "MMM d, yyyy 'at' h:mm a")}
															</p>
															{note.updated_at && (
																<p>
																	{t("updated") || "Updated"}:{" "}
																	{format(new Date(note.updated_at), "MMM d, yyyy 'at' h:mm a")}
																</p>
															)}
														</div>
													</TooltipContent>
												</Tooltip>

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
															<span className="sr-only">{t("more_options") || "More options"}</span>
														</Button>
													</DropdownMenuTrigger>
													<DropdownMenuContent align="end" className="w-40">
														<DropdownMenuItem
															onClick={() => handleDeleteNote(note.id, note.search_space_id)}
															className="text-destructive focus:text-destructive"
														>
															<Trash2 className="mr-2 h-4 w-4" />
															<span>{t("delete") || "Delete"}</span>
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

						{/* Footer with Add Note button */}
						{onAddNote && notes.length > 0 && (
							<div className="flex-shrink-0 p-3">
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
					</motion.div>
				</>
			)}
		</AnimatePresence>,
		document.body
	);
}
