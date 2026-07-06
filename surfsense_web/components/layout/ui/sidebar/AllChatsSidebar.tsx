"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import {
	ArchiveIcon,
	Check,
	ChevronDown,
	MoreHorizontal,
	Pencil,
	RotateCcwIcon,
	Search,
	Trash2,
	Users,
	X,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { removeChatTabAtom } from "@/atoms/tabs/tabs.atom";
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
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useActivateChatThread } from "@/hooks/use-activate-chat-thread";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useLongPress } from "@/hooks/use-long-press";
import { useIsMobile } from "@/hooks/use-mobile";
import { useArchiveThread, useDeleteThread, useRenameThread } from "@/hooks/use-thread-mutations";
import { fetchThreads, searchThreads, type ThreadListItem } from "@/lib/chat/thread-persistence";
import { formatThreadTimestamp } from "@/lib/format-date";
import { cn } from "@/lib/utils";

interface AllChatsContentProps {
	searchSpaceId: string;
	className?: string;
}

function AllChatsContent({ searchSpaceId, className }: AllChatsContentProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const queryClient = useQueryClient();
	const isMobile = useIsMobile();
	const removeChatTab = useSetAtom(removeChatTabAtom);
	const { activateChatThread, prefetchChatThread } = useActivateChatThread();
	const { mutateAsync: deleteThread } = useDeleteThread(searchSpaceId);
	const { mutateAsync: archiveThread } = useArchiveThread(searchSpaceId);
	const { mutateAsync: renameThread } = useRenameThread(searchSpaceId);

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

	const pendingThreadIdRef = useRef<number | null>(null);
	const { handlers: longPressHandlers, wasLongPress } = useLongPress(
		useCallback(() => {
			if (pendingThreadIdRef.current !== null) {
				setOpenDropdownId(pendingThreadIdRef.current);
			}
		}, [])
	);

	const isSearchMode = !!debouncedSearchQuery.trim();

	const {
		data: threadsData,
		error: threadsError,
		isLoading: isLoadingThreads,
	} = useQuery({
		queryKey: ["all-threads", searchSpaceId],
		queryFn: () => fetchThreads(Number(searchSpaceId)),
		enabled: !!searchSpaceId && !isSearchMode,
		placeholderData: () => queryClient.getQueryData(["threads", searchSpaceId, { limit: 40 }]),
	});

	const {
		data: searchData,
		error: searchError,
		isLoading: isLoadingSearch,
	} = useQuery({
		queryKey: ["search-threads", searchSpaceId, debouncedSearchQuery],
		queryFn: () => searchThreads(Number(searchSpaceId), debouncedSearchQuery.trim()),
		enabled: !!searchSpaceId && isSearchMode,
	});

	const threads = useMemo(() => {
		if (isSearchMode) {
			return (searchData ?? []).filter((thread) => thread.archived === showArchived);
		}

		if (!threadsData) return [];

		return showArchived ? threadsData.archived_threads : threadsData.threads;
	}, [threadsData, searchData, isSearchMode, showArchived]);

	const handleThreadClick = useCallback(
		(thread: ThreadListItem) => {
			activateChatThread({
				id: thread.id,
				title: thread.title || "New Chat",
				searchSpaceId,
				visibility: thread.visibility,
			});
		},
		[activateChatThread, searchSpaceId]
	);

	const handleDeleteThread = useCallback(
		async (threadId: number) => {
			setDeletingThreadId(threadId);
			try {
				await deleteThread({ threadId });
				const fallbackTab = removeChatTab(threadId);
				toast.success(t("chat_deleted") || "Chat deleted successfully");

				if (currentChatId === threadId) {
					setTimeout(() => {
						if (
							fallbackTab?.type === "chat" &&
							fallbackTab.chatUrl &&
							fallbackTab.chatId !== undefined
						) {
							activateChatThread({
								id: fallbackTab.chatId ?? null,
								title: fallbackTab.title,
								url: fallbackTab.chatUrl,
								searchSpaceId: fallbackTab.searchSpaceId ?? searchSpaceId,
								...(fallbackTab.visibility !== undefined
									? { visibility: fallbackTab.visibility }
									: {}),
								...(fallbackTab.hasComments !== undefined
									? { hasComments: fallbackTab.hasComments }
									: {}),
							});
							return;
						}
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
		[activateChatThread, deleteThread, t, currentChatId, router, removeChatTab, searchSpaceId]
	);

	const handleToggleArchive = useCallback(
		async (threadId: number, currentlyArchived: boolean) => {
			setArchivingThreadId(threadId);
			try {
				await archiveThread({ threadId, archived: !currentlyArchived });
				toast.success(
					currentlyArchived
						? t("chat_unarchived") || "Chat restored"
						: t("chat_archived") || "Chat archived"
				);
			} catch (error) {
				console.error("Error archiving thread:", error);
				toast.error(t("error_archiving_chat") || "Failed to archive chat");
			} finally {
				setArchivingThreadId(null);
			}
		},
		[archiveThread, t]
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
			await renameThread({
				threadId: renamingThread.id,
				title: newTitle.trim(),
				previousTitle: renamingThread.title,
			});
			toast.success(t("chat_renamed") || "Chat renamed");
		} catch (error) {
			console.error("Error renaming thread:", error);
			toast.error(t("error_renaming_chat") || "Failed to rename chat");
		} finally {
			setIsRenaming(false);
			setShowRenameDialog(false);
			setRenamingThread(null);
			setNewTitle("");
		}
	}, [renamingThread, newTitle, renameThread, t]);

	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	const isLoading = isSearchMode ? isLoadingSearch : isLoadingThreads;
	const error = isSearchMode ? searchError : threadsError;

	const selectedFilterLabel = showArchived ? "Archived" : "Active";

	return (
		<div className={cn("flex h-full min-h-0 w-full flex-1 flex-col", className)}>
			<div className="shrink-0 space-y-4 px-3 pb-3 pt-3">
				<div className="flex items-center justify-between gap-4 flex-wrap">
					<div className="flex items-baseline gap-3">
						<h1 className="text-xl md:text-2xl font-semibold text-foreground">
							{t("chats") || "Chats"}
						</h1>
					</div>
					{!isSearchMode && (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									type="button"
									variant="secondary"
									className="h-7 gap-1.5 rounded-md px-2.5 text-xs font-medium"
								>
									<span className="text-muted-foreground">Filter by</span>
									<span>{selectedFilterLabel}</span>
									<ChevronDown className="h-3 w-3 text-muted-foreground" />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="end" className="w-32">
								<DropdownMenuItem onClick={() => setShowArchived(false)}>
									<span className="flex-1">Active</span>
									<Check
										className={cn(
											"h-4 w-4 text-primary",
											showArchived ? "opacity-0" : "opacity-100"
										)}
									/>
								</DropdownMenuItem>
								<DropdownMenuItem onClick={() => setShowArchived(true)}>
									<span className="flex-1">Archived</span>
									<Check
										className={cn(
											"h-4 w-4 text-primary",
											showArchived ? "opacity-100" : "opacity-0"
										)}
									/>
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					)}
				</div>

				<div className="relative">
					<Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-muted-foreground" />
					<Input
						type="text"
						placeholder={t("search_chats") || "Search chats..."}
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						className="h-12 border-0 bg-muted pl-10 pr-9 text-base shadow-none"
					/>
					{searchQuery && (
						<Button
							variant="ghost"
							size="icon"
							className="absolute right-2 top-1/2 h-7 w-7 -translate-y-1/2 rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
							onClick={handleClearSearch}
						>
							<X className="h-4.5 w-4.5" />
							<span className="sr-only">{t("clear_search") || "Clear search"}</span>
						</Button>
					)}
				</div>
			</div>

			<div className="flex-1 overflow-y-auto overflow-x-hidden p-1.5">
				{isLoading ? (
					<div className="space-y-1">
						{[75, 90, 55, 80, 65, 85].map((titleWidth) => (
							<div
								key={`skeleton-${titleWidth}`}
								className="flex items-center gap-2.5 rounded-md px-3 py-2.5"
							>
								<Skeleton className="h-4 w-4 shrink-0 rounded" />
								<Skeleton className="h-5 rounded" style={{ width: `${titleWidth}%` }} />
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
								<div key={thread.id} className="group/item relative w-full">
									{isMobile ? (
										<Button
											type="button"
											variant="ghost"
											onClick={() => {
												if (wasLongPress()) return;
												handleThreadClick(thread);
											}}
											onMouseEnter={() => prefetchChatThread(thread.id)}
											onFocus={() => prefetchChatThread(thread.id)}
											onTouchStart={() => {
												pendingThreadIdRef.current = thread.id;
												longPressHandlers.onTouchStart();
											}}
											onTouchEnd={longPressHandlers.onTouchEnd}
											onTouchMove={longPressHandlers.onTouchMove}
											disabled={isBusy}
											className={cn(
												"h-auto w-full justify-start gap-2.5 overflow-hidden px-3 py-2.5 text-left text-base font-normal",
												"group-hover/item:bg-accent group-hover/item:text-accent-foreground",
												"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
												thread.visibility === "SEARCH_SPACE" && "pr-10",
												isActive && "bg-accent text-accent-foreground",
												isBusy && "opacity-50 pointer-events-none"
											)}
										>
											<span className="min-w-0 flex-1 truncate">{thread.title || "New Chat"}</span>
										</Button>
									) : (
										<Tooltip delayDuration={600}>
											<TooltipTrigger asChild>
												<Button
													type="button"
													variant="ghost"
													onClick={() => handleThreadClick(thread)}
													onMouseEnter={() => prefetchChatThread(thread.id)}
													onFocus={() => prefetchChatThread(thread.id)}
													disabled={isBusy}
													className={cn(
														"h-auto w-full justify-start gap-2.5 overflow-hidden px-3 py-2.5 text-left text-base font-normal",
														"group-hover/item:bg-accent group-hover/item:text-accent-foreground",
														"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
														thread.visibility === "SEARCH_SPACE" && "pr-10",
														isActive && "bg-accent text-accent-foreground",
														isBusy && "opacity-50 pointer-events-none"
													)}
												>
													<span className="min-w-0 flex-1 truncate">
														{thread.title || "New Chat"}
													</span>
												</Button>
											</TooltipTrigger>
											<TooltipContent side="bottom" align="start">
												<p>
													{t("updated") || "Updated"}: {formatThreadTimestamp(thread.updatedAt)}
												</p>
											</TooltipContent>
										</Tooltip>
									)}

									<div
										className={cn(
											"pointer-events-none absolute inset-y-0 right-0 flex items-center rounded-r-md pl-6 pr-1",
											isActive
												? "bg-gradient-to-l from-accent from-60% to-transparent"
												: "bg-gradient-to-l from-sidebar from-60% to-transparent group-hover/item:from-accent",
											isMobile
												? "opacity-0"
												: thread.visibility === "SEARCH_SPACE" || openDropdownId === thread.id
													? "opacity-100"
													: "opacity-0 group-hover/item:opacity-100"
										)}
									>
										<div className="relative flex h-7 w-7 items-center justify-center">
											{thread.visibility === "SEARCH_SPACE" ? (
												<Users
													aria-label={t("shared_chat") || "Shared chat"}
													className={cn(
														"absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/50",
														!isMobile &&
															(openDropdownId === thread.id
																? "opacity-0"
																: "opacity-100 group-hover/item:opacity-0")
													)}
												/>
											) : null}
											<DropdownMenu
												open={openDropdownId === thread.id}
												onOpenChange={(isOpen) => setOpenDropdownId(isOpen ? thread.id : null)}
											>
												<DropdownMenuTrigger asChild>
													<Button
														variant="ghost"
														size="icon"
														className={cn(
															"pointer-events-auto h-7 w-7 hover:bg-transparent",
															openDropdownId === thread.id && "bg-accent hover:bg-accent",
															!isMobile &&
																openDropdownId !== thread.id &&
																"opacity-0 group-hover/item:opacity-100"
														)}
														disabled={isBusy}
													>
														{isDeleting ? (
															<Spinner size="xs" />
														) : (
															<MoreHorizontal className="h-4 w-4 text-muted-foreground" />
														)}
														<span className="sr-only">{t("more_options") || "More options"}</span>
													</Button>
												</DropdownMenuTrigger>
												<DropdownMenuContent align="end" className="w-40 z-80">
													{!thread.archived && (
														<DropdownMenuItem
															onClick={() =>
																handleStartRename(thread.id, thread.title || "New Chat")
															}
														>
															<Pencil className="mr-2 h-4 w-4" />
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
													<DropdownMenuItem onClick={() => handleDeleteThread(thread.id)}>
														<Trash2 className="mr-2 h-4 w-4" />
														<span>{t("delete") || "Delete"}</span>
													</DropdownMenuItem>
												</DropdownMenuContent>
											</DropdownMenu>
										</div>
									</div>
								</div>
							);
						})}
					</div>
				) : isSearchMode ? (
					<div className="text-center py-8">
						<Search className="mx-auto mb-2.5 h-10 w-10 text-muted-foreground" />
						<p className="text-xs text-muted-foreground">
							{t("no_chats_found") || "No chats found"}
						</p>
						<p className="mt-1 text-[11px] text-muted-foreground/70">
							{t("try_different_search") || "Try a different search term"}
						</p>
					</div>
				) : (
					<div className="text-center py-8">
						<p className="text-base font-medium text-muted-foreground">
							{showArchived
								? t("no_archived_chats") || "No archived chats"
								: t("no_chats") || "No chats"}
						</p>
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
					<DialogFooter className="flex sm:justify-end">
						<Button
							variant="secondary"
							onClick={() => setShowRenameDialog(false)}
							disabled={isRenaming}
						>
							{t("cancel")}
						</Button>
						<Button
							onClick={handleConfirmRename}
							disabled={isRenaming || !newTitle.trim()}
							className="relative"
						>
							<span className={isRenaming ? "opacity-0" : undefined}>
								{t("rename") || "Rename"}
							</span>
							{isRenaming ? (
								<Spinner
									size="xs"
									className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
								/>
							) : null}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}

export function AllChatsWorkspaceContent({ searchSpaceId }: { searchSpaceId: string }) {
	return (
		<div className="flex h-[calc(100vh-8rem)] min-h-0 w-full overflow-hidden text-sidebar-foreground">
			<AllChatsContent searchSpaceId={searchSpaceId} />
		</div>
	);
}
