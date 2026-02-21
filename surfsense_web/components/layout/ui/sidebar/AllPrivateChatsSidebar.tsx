"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
	ArchiveIcon,
	ChevronLeft,
	MessageCircleMore,
	MoreHorizontal,
	PenLine,
	RotateCcwIcon,
	Search,
	Trash2,
	User,
	X,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useIsMobile } from "@/hooks/use-mobile";
import {
	deleteThread,
	fetchThreads,
	searchThreads,
	updateThread,
} from "@/lib/chat/thread-persistence";
import { cn } from "@/lib/utils";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

interface AllPrivateChatsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: string;
	onCloseMobileSidebar?: () => void;
}

export function AllPrivateChatsSidebar({
	open,
	onOpenChange,
	searchSpaceId,
	onCloseMobileSidebar,
}: AllPrivateChatsSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const queryClient = useQueryClient();
	const isMobile = useIsMobile();

	const currentChatId = Array.isArray(params.chat_id)
		? Number(params.chat_id[0])
		: params.chat_id
			? Number(params.chat_id)
			: null;
	const [deletingThreadId, setDeletingThreadId] = useState<number | null>(null);
	const [archivingThreadId, setArchivingThreadId] = useState<number | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [showArchived, setShowArchived] = useState(false);
	const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
	const [showRenameDialog, setShowRenameDialog] = useState(false);
	const [renamingThread, setRenamingThread] = useState<{ id: number; title: string } | null>(null);
	const [newTitle, setNewTitle] = useState("");
	const [isRenaming, setIsRenaming] = useState(false);
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	const isSearchMode = !!debouncedSearchQuery.trim();

	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) {
				onOpenChange(false);
			}
		};
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

	const {
		data: threadsData,
		error: threadsError,
		isLoading: isLoadingThreads,
	} = useQuery({
		queryKey: ["all-threads", searchSpaceId],
		queryFn: () => fetchThreads(Number(searchSpaceId)),
		enabled: !!searchSpaceId && open && !isSearchMode,
	});

	const {
		data: searchData,
		error: searchError,
		isLoading: isLoadingSearch,
	} = useQuery({
		queryKey: ["search-threads", searchSpaceId, debouncedSearchQuery],
		queryFn: () => searchThreads(Number(searchSpaceId), debouncedSearchQuery.trim()),
		enabled: !!searchSpaceId && open && isSearchMode,
	});

	// Filter to only private chats (PRIVATE visibility or no visibility set)
	const { activeChats, archivedChats } = useMemo(() => {
		if (isSearchMode) {
			const privateSearchResults = (searchData ?? []).filter(
				(thread) => thread.visibility !== "SEARCH_SPACE"
			);
			return {
				activeChats: privateSearchResults.filter((t) => !t.archived),
				archivedChats: privateSearchResults.filter((t) => t.archived),
			};
		}

		if (!threadsData) return { activeChats: [], archivedChats: [] };

		const activePrivate = threadsData.threads.filter(
			(thread) => thread.visibility !== "SEARCH_SPACE"
		);
		const archivedPrivate = threadsData.archived_threads.filter(
			(thread) => thread.visibility !== "SEARCH_SPACE"
		);

		return { activeChats: activePrivate, archivedChats: archivedPrivate };
	}, [threadsData, searchData, isSearchMode]);

	const threads = showArchived ? archivedChats : activeChats;

	const handleThreadClick = useCallback(
		(threadId: number) => {
			router.push(`/dashboard/${searchSpaceId}/new-chat/${threadId}`);
			onOpenChange(false);
			onCloseMobileSidebar?.();
		},
		[router, onOpenChange, searchSpaceId, onCloseMobileSidebar]
	);

	const handleDeleteThread = useCallback(
		async (threadId: number) => {
			setDeletingThreadId(threadId);
			try {
				await deleteThread(threadId);
				toast.success(t("chat_deleted") || "Chat deleted successfully");
				queryClient.invalidateQueries({ queryKey: ["all-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["search-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });

				if (currentChatId === threadId) {
					onOpenChange(false);
					setTimeout(() => {
						router.push(`/dashboard/${searchSpaceId}/new-chat`);
					}, 250);
				}
			} catch (error) {
				console.error("Error deleting thread:", error);
				toast.error(t("error_deleting_chat") || "Failed to delete chat");
			} finally {
				setDeletingThreadId(null);
			}
		},
		[queryClient, searchSpaceId, t, currentChatId, router, onOpenChange]
	);

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

	const handleStartRename = useCallback((threadId: number, title: string) => {
		setRenamingThread({ id: threadId, title });
		setNewTitle(title);
		setShowRenameDialog(true);
	}, []);

	const handleConfirmRename = useCallback(async () => {
		if (!renamingThread || !newTitle.trim()) return;
		setIsRenaming(true);
		try {
			await updateThread(renamingThread.id, { title: newTitle.trim() });
			toast.success(t("chat_renamed") || "Chat renamed");
			queryClient.invalidateQueries({ queryKey: ["all-threads", searchSpaceId] });
			queryClient.invalidateQueries({ queryKey: ["search-threads", searchSpaceId] });
			queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
			queryClient.invalidateQueries({
				queryKey: ["threads", searchSpaceId, "detail", String(renamingThread.id)],
			});
		} catch (error) {
			console.error("Error renaming thread:", error);
			toast.error(t("error_renaming_chat") || "Failed to rename chat");
		} finally {
			setIsRenaming(false);
			setShowRenameDialog(false);
			setRenamingThread(null);
			setNewTitle("");
		}
	}, [renamingThread, newTitle, queryClient, searchSpaceId, t]);

	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	const isLoading = isSearchMode ? isLoadingSearch : isLoadingThreads;
	const error = isSearchMode ? searchError : threadsError;

	const activeCount = activeChats.length;
	const archivedCount = archivedChats.length;

	return (
		<SidebarSlideOutPanel
			open={open}
			onOpenChange={onOpenChange}
			ariaLabel={t("chats") || "Private Chats"}
		>
			<div className="shrink-0 p-4 pb-2 space-y-3">
				<div className="flex items-center gap-2">
					{isMobile && (
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8 rounded-full"
							onClick={() => onOpenChange(false)}
						>
							<ChevronLeft className="h-4 w-4 text-muted-foreground" />
							<span className="sr-only">{t("close") || "Close"}</span>
						</Button>
					)}
					<User className="h-5 w-5 text-primary" />
					<h2 className="text-lg font-semibold">{t("chats") || "Private Chats"}</h2>
				</div>

				<div className="relative">
					<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
					<Input
						type="text"
						placeholder={t("search_chats") || "Search chats..."}
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

			{!isSearchMode && (
				<Tabs
					value={showArchived ? "archived" : "active"}
					onValueChange={(value) => setShowArchived(value === "archived")}
					className="shrink-0 mx-4"
				>
					<TabsList className="w-full h-auto p-0 bg-transparent rounded-none border-b">
						<TabsTrigger
							value="active"
							className="flex-1 rounded-none border-b-2 border-transparent px-1 py-2 text-xs font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
						>
							<span className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-muted transition-colors">
								<MessageCircleMore className="h-4 w-4" />
								<span>Active</span>
								<span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium">
									{activeCount}
								</span>
							</span>
						</TabsTrigger>
						<TabsTrigger
							value="archived"
							className="flex-1 rounded-none border-b-2 border-transparent px-1 py-2 text-xs font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
						>
							<span className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-muted transition-colors">
								<ArchiveIcon className="h-4 w-4" />
								<span>Archived</span>
								<span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium">
									{archivedCount}
								</span>
							</span>
						</TabsTrigger>
					</TabsList>
				</Tabs>
			)}

			<div className="flex-1 overflow-y-auto overflow-x-hidden p-2">
				{isLoading ? (
					<div className="space-y-1">
						{[75, 90, 55, 80, 65, 85].map((titleWidth, i) => (
							<div key={`skeleton-${i}`} className="flex items-center gap-2 rounded-md px-2 py-1.5">
								<Skeleton className="h-4 w-4 shrink-0 rounded" />
								<Skeleton className="h-4 rounded" style={{ width: `${titleWidth}%` }} />
							</div>
						))}
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
							const isActive = currentChatId === thread.id;

							return (
								<div
									key={thread.id}
									className={cn(
										"group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
										"hover:bg-accent hover:text-accent-foreground",
										"transition-colors cursor-pointer",
										isActive && "bg-accent text-accent-foreground",
										isBusy && "opacity-50 pointer-events-none"
									)}
								>
									{isMobile ? (
										<button
											type="button"
											onClick={() => handleThreadClick(thread.id)}
											disabled={isBusy}
											className="flex items-center gap-2 flex-1 min-w-0 text-left overflow-hidden"
										>
											<MessageCircleMore className="h-4 w-4 shrink-0 text-muted-foreground" />
											<span className="truncate">{thread.title || "New Chat"}</span>
										</button>
									) : (
										<Tooltip>
											<TooltipTrigger asChild>
												<button
													type="button"
													onClick={() => handleThreadClick(thread.id)}
													disabled={isBusy}
													className="flex items-center gap-2 flex-1 min-w-0 text-left overflow-hidden"
												>
													<MessageCircleMore className="h-4 w-4 shrink-0 text-muted-foreground" />
													<span className="truncate">{thread.title || "New Chat"}</span>
												</button>
											</TooltipTrigger>
											<TooltipContent side="bottom" align="start">
												<p>
													{t("updated") || "Updated"}:{" "}
													{format(new Date(thread.updatedAt), "MMM d, yyyy 'at' h:mm a")}
												</p>
											</TooltipContent>
										</Tooltip>
									)}

									<DropdownMenu
										open={openDropdownId === thread.id}
										onOpenChange={(isOpen) => setOpenDropdownId(isOpen ? thread.id : null)}
									>
										<DropdownMenuTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className={cn(
													"h-6 w-6 shrink-0",
													"md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100",
													"transition-opacity"
												)}
												disabled={isBusy}
											>
												{isDeleting ? (
													<Spinner size="xs" />
												) : (
													<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
												)}
												<span className="sr-only">{t("more_options") || "More options"}</span>
											</Button>
										</DropdownMenuTrigger>
										<DropdownMenuContent align="end" className="w-40 z-80">
											{!thread.archived && (
												<DropdownMenuItem
													onClick={() => handleStartRename(thread.id, thread.title || "New Chat")}
												>
													<PenLine className="mr-2 h-4 w-4" />
													<span>{t("rename") || "Rename"}</span>
												</DropdownMenuItem>
											)}
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
						<Search className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
						<p className="text-sm text-muted-foreground">
							{t("no_chats_found") || "No chats found"}
						</p>
						<p className="text-xs text-muted-foreground/70 mt-1">
							{t("try_different_search") || "Try a different search term"}
						</p>
					</div>
				) : (
					<div className="text-center py-8">
						<User className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
						<p className="text-sm text-muted-foreground">
							{showArchived
								? t("no_archived_chats") || "No archived chats"
								: t("no_chats") || "No private chats"}
						</p>
						{!showArchived && (
							<p className="text-xs text-muted-foreground/70 mt-1">
								{t("start_new_chat_hint") || "Start a new chat from the chat page"}
							</p>
						)}
					</div>
				)}
			</div>
			<Dialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<span>{t("rename_chat") || "Rename Chat"}</span>
						</DialogTitle>
						<DialogDescription>
							{t("rename_chat_description") || "Enter a new name for this conversation."}
						</DialogDescription>
					</DialogHeader>
					<Input
						value={newTitle}
						onChange={(e) => setNewTitle(e.target.value)}
						placeholder={t("chat_title_placeholder") || "Chat title"}
						onKeyDown={(e) => {
							if (e.key === "Enter" && !isRenaming && newTitle.trim()) {
								handleConfirmRename();
							}
						}}
					/>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowRenameDialog(false)}
							disabled={isRenaming}
						>
							{t("cancel")}
						</Button>
						<Button
							onClick={handleConfirmRename}
							disabled={isRenaming || !newTitle.trim()}
							className="gap-2"
						>
							{isRenaming ? (
								<>
									<Spinner size="xs" />
									<span>{t("renaming") || "Renaming"}</span>
								</>
							) : (
								<span>{t("rename") || "Rename"}</span>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</SidebarSlideOutPanel>
	);
}
