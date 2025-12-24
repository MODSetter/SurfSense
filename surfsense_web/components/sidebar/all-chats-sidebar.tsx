"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
	ArchiveIcon,
	Loader2,
	MessageCircleMore,
	MoreHorizontal,
	RotateCcwIcon,
	Search,
	Trash2,
	X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import {
	deleteThread,
	fetchThreads,
	searchThreads,
	type ThreadListItem,
	updateThread,
} from "@/lib/chat/thread-persistence";
import { cn } from "@/lib/utils";

interface AllChatsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: string;
}

export function AllChatsSidebar({ open, onOpenChange, searchSpaceId }: AllChatsSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const queryClient = useQueryClient();
	const [deletingThreadId, setDeletingThreadId] = useState<number | null>(null);
	const [archivingThreadId, setArchivingThreadId] = useState<number | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [showArchived, setShowArchived] = useState(false);
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	const isSearchMode = !!debouncedSearchQuery.trim();

	// Fetch all threads (when not searching)
	const {
		data: threadsData,
		error: threadsError,
		isLoading: isLoadingThreads,
	} = useQuery({
		queryKey: ["all-threads", searchSpaceId],
		queryFn: () => fetchThreads(Number(searchSpaceId)),
		enabled: !!searchSpaceId && open && !isSearchMode,
	});

	// Search threads (when searching)
	const {
		data: searchData,
		error: searchError,
		isLoading: isLoadingSearch,
	} = useQuery({
		queryKey: ["search-threads", searchSpaceId, debouncedSearchQuery],
		queryFn: () => searchThreads(Number(searchSpaceId), debouncedSearchQuery.trim()),
		enabled: !!searchSpaceId && open && isSearchMode,
	});

	// Handle thread navigation
	const handleThreadClick = useCallback(
		(threadId: number) => {
			router.push(`/dashboard/${searchSpaceId}/new-chat/${threadId}`);
			onOpenChange(false);
		},
		[router, onOpenChange, searchSpaceId]
	);

	// Handle thread deletion
	const handleDeleteThread = useCallback(
		async (threadId: number) => {
			setDeletingThreadId(threadId);
			try {
				await deleteThread(threadId);
				toast.success(t("chat_deleted") || "Chat deleted successfully");
				// Invalidate queries to refresh the list
				queryClient.invalidateQueries({ queryKey: ["all-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["search-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
			} catch (error) {
				console.error("Error deleting thread:", error);
				toast.error(t("error_deleting_chat") || "Failed to delete chat");
			} finally {
				setDeletingThreadId(null);
			}
		},
		[queryClient, searchSpaceId, t]
	);

	// Handle thread archive/unarchive
	const handleToggleArchive = useCallback(
		async (threadId: number, currentlyArchived: boolean) => {
			setArchivingThreadId(threadId);
			try {
				await updateThread(threadId, { archived: !currentlyArchived });
				toast.success(
					currentlyArchived
						? t("chat_unarchived") || "Chat restored"
						: t("chat_archived") || "Chat archived"
				);
				queryClient.invalidateQueries({ queryKey: ["all-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["search-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
			} catch (error) {
				console.error("Error archiving thread:", error);
				toast.error(t("error_archiving_chat") || "Failed to archive chat");
			} finally {
				setArchivingThreadId(null);
			}
		},
		[queryClient, searchSpaceId, t]
	);

	// Clear search
	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	// Determine which data source to use
	let threads: ThreadListItem[] = [];
	if (isSearchMode) {
		threads = searchData ?? [];
	} else if (threadsData) {
		threads = showArchived ? threadsData.archived_threads : threadsData.threads;
	}

	const isLoading = isSearchMode ? isLoadingSearch : isLoadingThreads;
	const error = isSearchMode ? searchError : threadsError;

	// Get counts for tabs
	const activeCount = threadsData?.threads.length ?? 0;
	const archivedCount = threadsData?.archived_threads.length ?? 0;

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="left" className="w-80 p-0 flex flex-col border-0">
				<SheetHeader className="mx-3 px-4 pt-4 pb-0 space-y-2">
					<SheetTitle>{t("all_chats") || "All Chats"}</SheetTitle>
					<SheetDescription className="sr-only">
						{t("all_chats_description") || "Browse and manage all your chats"}
					</SheetDescription>

					{/* Search Input */}
					<div className="relative">
						<Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
						<Input
							type="text"
							placeholder={t("search_chats") || "Search chats..."}
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							className="pl-9 pr-8 h-9 border-0 focus-visible:ring-0 focus-visible:border-0 shadow-none"
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
				</SheetHeader>

				{/* Tab toggle for active/archived (only show when not searching) */}
				{!isSearchMode && (
					<div className="flex border-b mx-3 -mt-3">
						<button
							type="button"
							onClick={() => setShowArchived(false)}
							className={cn(
								"flex-1 px-3 py-2 text-center text-xs font-medium transition-colors",
								!showArchived
									? "border-b-2 border-primary text-primary"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							Active ({activeCount})
						</button>
						<button
							type="button"
							onClick={() => setShowArchived(true)}
							className={cn(
								"flex-1 px-3 py-2 text-center text-xs font-medium transition-colors",
								showArchived
									? "border-b-2 border-primary text-primary"
									: "text-muted-foreground hover:text-foreground"
							)}
						>
							Archived ({archivedCount})
						</button>
					</div>
				)}

				<ScrollArea className="flex-1 min-h-0 overflow-hidden">
					<div className="p-2">
						{isLoading ? (
							<div className="flex items-center justify-center py-8">
								<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
							</div>
						) : error ? (
							<div className="text-center py-8 text-sm text-destructive">
								{t("error_loading_chats") || "Error loading chats"}
							</div>
						) : threads.length > 0 ? (
							<div className="space-y-1">
								{threads.map((thread) => {
									const isDeleting = deletingThreadId === thread.id;
									const isArchiving = archivingThreadId === thread.id;
									const isBusy = isDeleting || isArchiving;

									return (
										<div
											key={thread.id}
											className={cn(
												"group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
												"hover:bg-accent hover:text-accent-foreground",
												"transition-colors cursor-pointer",
												isBusy && "opacity-50 pointer-events-none"
											)}
										>
											{/* Main clickable area for navigation */}
											<Tooltip>
												<TooltipTrigger asChild>
													<button
														type="button"
														onClick={() => handleThreadClick(thread.id)}
														disabled={isBusy}
														className="flex items-center gap-2 flex-1 min-w-0 text-left"
													>
														<MessageCircleMore className="h-4 w-4 shrink-0 text-muted-foreground" />
														<span className="truncate">{thread.title || "New Chat"}</span>
													</button>
												</TooltipTrigger>
												<TooltipContent side="right">
													<p>
														{t("updated") || "Updated"}:{" "}
														{format(new Date(thread.updatedAt), "MMM d, yyyy 'at' h:mm a")}
													</p>
												</TooltipContent>
											</Tooltip>

											{/* Actions dropdown */}
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
														disabled={isBusy}
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
														onClick={() => handleToggleArchive(thread.id, thread.archived)}
														disabled={isArchiving}
													>
														{thread.archived ? (
															<>
																<RotateCcwIcon className="mr-2 h-4 w-4" />
																<span>{t("unarchive") || "Restore"}</span>
															</>
														) : (
															<>
																<ArchiveIcon className="mr-2 h-4 w-4" />
																<span>{t("archive") || "Archive"}</span>
															</>
														)}
													</DropdownMenuItem>
													<DropdownMenuSeparator />
													<DropdownMenuItem
														onClick={() => handleDeleteThread(thread.id)}
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
									{t("no_chats_found") || "No chats found"}
								</p>
								<p className="text-xs text-muted-foreground/70 mt-1">
									{t("try_different_search") || "Try a different search term"}
								</p>
							</div>
						) : (
							<div className="text-center py-8">
								<MessageCircleMore className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
								<p className="text-sm text-muted-foreground">
									{showArchived
										? t("no_archived_chats") || "No archived chats"
										: t("no_chats") || "No chats yet"}
								</p>
								{!showArchived && (
									<p className="text-xs text-muted-foreground/70 mt-1">
										{t("start_new_chat_hint") || "Start a new chat from the chat page"}
									</p>
								)}
							</div>
						)}
					</div>
				</ScrollArea>
			</SheetContent>
		</Sheet>
	);
}
