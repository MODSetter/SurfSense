"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
	ArchiveIcon,
	MessageCircleMore,
	MoreHorizontal,
	RotateCcwIcon,
	Search,
	Trash2,
	User,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
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
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import {
	deleteThread,
	fetchThreads,
	searchThreads,
	updateThread,
} from "@/lib/chat/thread-persistence";
import { cn } from "@/lib/utils";

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

	const currentChatId = Array.isArray(params.chat_id)
		? Number(params.chat_id[0])
		: params.chat_id
			? Number(params.chat_id)
			: null;
	const [deletingThreadId, setDeletingThreadId] = useState<number | null>(null);
	const [archivingThreadId, setArchivingThreadId] = useState<number | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [showArchived, setShowArchived] = useState(false);
	const [mounted, setMounted] = useState(false);
	const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	const isSearchMode = !!debouncedSearchQuery.trim();

	useEffect(() => {
		setMounted(true);
	}, []);

	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && open) {
				onOpenChange(false);
			}
		};
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

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

	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	const isLoading = isSearchMode ? isLoadingSearch : isLoadingThreads;
	const error = isSearchMode ? searchError : threadsError;

	const activeCount = activeChats.length;
	const archivedCount = archivedChats.length;

	if (!mounted) return null;

	return createPortal(
		<AnimatePresence>
			{open && (
				<>
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="fixed inset-0 z-70 bg-black/50"
						onClick={() => onOpenChange(false)}
						aria-hidden="true"
					/>

					<motion.div
						initial={{ x: "-100%" }}
						animate={{ x: 0 }}
						exit={{ x: "-100%" }}
						transition={{ type: "tween", duration: 0.3, ease: "easeOut" }}
						className="fixed inset-y-0 left-0 z-70 w-80 bg-background shadow-xl flex flex-col pointer-events-auto isolate"
						role="dialog"
						aria-modal="true"
						aria-label={t("chats") || "Private Chats"}
					>
						<div className="shrink-0 p-4 pb-2 space-y-3">
							<div className="flex items-center gap-2">
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
								<div className="flex items-center justify-center py-8">
									<Spinner size="md" className="text-muted-foreground" />
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
					</motion.div>
				</>
			)}
		</AnimatePresence>,
		document.body
	);
}
