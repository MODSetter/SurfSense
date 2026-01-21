"use client";

import {
	AlertCircle,
	Archive,
	AtSign,
	BellDot,
	Check,
	CheckCheck,
	CheckCircle2,
	History,
	Inbox,
	ListFilter,
	MoreHorizontal,
	RotateCcw,
	Search,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { convertRenderedToDisplay } from "@/components/chat-comments/comment-item/comment-item";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { InboxItem } from "@/hooks/use-inbox";
import { cn } from "@/lib/utils";

/**
 * Get initials from name or email for avatar fallback
 */
function getInitials(name: string | null | undefined, email: string | null | undefined): string {
	if (name) {
		return name
			.split(" ")
			.map((n) => n[0])
			.join("")
			.toUpperCase()
			.slice(0, 2);
	}
	if (email) {
		const localPart = email.split("@")[0];
		return localPart.slice(0, 2).toUpperCase();
	}
	return "U";
}

type InboxTab = "mentions" | "status";
type InboxFilter = "all" | "unread" | "archived";

interface InboxSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	inboxItems: InboxItem[];
	unreadCount: number;
	loading: boolean;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
	archiveItem: (id: number, archived: boolean) => Promise<boolean>;
	onCloseMobileSidebar?: () => void;
}

export function InboxSidebar({
	open,
	onOpenChange,
	inboxItems,
	unreadCount,
	loading,
	markAsRead,
	markAllAsRead,
	archiveItem,
	onCloseMobileSidebar,
}: InboxSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();

	const [searchQuery, setSearchQuery] = useState("");
	const [activeTab, setActiveTab] = useState<InboxTab>("mentions");
	const [activeFilter, setActiveFilter] = useState<InboxFilter>("all");
	const [mounted, setMounted] = useState(false);
	// Unified dropdown state: "filter" | "options" | number (item id) | null
	const [openDropdown, setOpenDropdown] = useState<"filter" | "options" | number | null>(null);
	const [markingAsReadId, setMarkingAsReadId] = useState<number | null>(null);
	const [archivingItemId, setArchivingItemId] = useState<number | null>(null);

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

	// Split items by type
	const mentionItems = useMemo(
		() => inboxItems.filter((item) => item.type === "new_mention"),
		[inboxItems]
	);

	const statusItems = useMemo(
		() =>
			inboxItems.filter(
				(item) => item.type === "connector_indexing" || item.type === "document_processing"
			),
		[inboxItems]
	);

	// Get items for current tab
	const currentTabItems = activeTab === "mentions" ? mentionItems : statusItems;

	// Filter items based on filter type and search query
	const filteredItems = useMemo(() => {
		let items = currentTabItems;

		// Apply filter
		// Note: Use `item.archived === true` to handle undefined/null as false
		if (activeFilter === "all") {
			// "Unread & read" shows all non-archived items
			items = items.filter((item) => item.archived !== true);
		} else if (activeFilter === "unread") {
			// "Unread" shows only unread non-archived items
			items = items.filter((item) => !item.read && item.archived !== true);
		} else if (activeFilter === "archived") {
			// "Archived" shows only archived items (must be explicitly true)
			items = items.filter((item) => item.archived === true);
		}

		// Apply search query
		if (searchQuery.trim()) {
			const query = searchQuery.toLowerCase();
			items = items.filter(
				(item) =>
					item.title.toLowerCase().includes(query) ||
					item.message.toLowerCase().includes(query)
			);
		}

		return items;
	}, [currentTabItems, activeFilter, searchQuery]);

	// Count unread items per tab (filter-aware)
	const unreadMentionsCount = useMemo(() => {
		if (activeFilter === "archived") {
			// In archived view, show unread archived items
			return mentionItems.filter((item) => !item.read && item.archived === true).length;
		}
		// For "all" and "unread" filters, show unread non-archived items
		return mentionItems.filter((item) => !item.read && item.archived !== true).length;
	}, [mentionItems, activeFilter]);

	const unreadStatusCount = useMemo(() => {
		if (activeFilter === "archived") {
			// In archived view, show unread archived items
			return statusItems.filter((item) => !item.read && item.archived === true).length;
		}
		// For "all" and "unread" filters, show unread non-archived items
		return statusItems.filter((item) => !item.read && item.archived !== true).length;
	}, [statusItems, activeFilter]);

	const handleItemClick = useCallback(
		async (item: InboxItem) => {
			if (!item.read) {
				setMarkingAsReadId(item.id);
				await markAsRead(item.id);
				setMarkingAsReadId(null);
			}

			if (item.type === "new_mention") {
				const metadata = item.metadata as {
					thread_id?: number;
					comment_id?: number;
				};
				const searchSpaceId = item.search_space_id;
				const threadId = metadata?.thread_id;
				const commentId = metadata?.comment_id;

				if (searchSpaceId && threadId) {
					const url = commentId
						? `/dashboard/${searchSpaceId}/new-chat/${threadId}?commentId=${commentId}`
						: `/dashboard/${searchSpaceId}/new-chat/${threadId}`;
					onOpenChange(false);
					onCloseMobileSidebar?.();
					router.push(url);
				}
			}
		},
		[markAsRead, router, onOpenChange, onCloseMobileSidebar]
	);

	const handleMarkAsRead = useCallback(
		async (itemId: number) => {
			setMarkingAsReadId(itemId);
			await markAsRead(itemId);
			setMarkingAsReadId(null);
		},
		[markAsRead]
	);

	const handleMarkAllAsRead = useCallback(async () => {
		await markAllAsRead();
	}, [markAllAsRead]);

	const handleToggleArchive = useCallback(
		async (itemId: number, currentlyArchived: boolean) => {
			setArchivingItemId(itemId);
			await archiveItem(itemId, !currentlyArchived);
			setArchivingItemId(null);
		},
		[archiveItem]
	);

	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	const formatTime = (dateString: string) => {
		try {
			const date = new Date(dateString);
			const now = new Date();
			const diffMs = now.getTime() - date.getTime();
			const diffMins = Math.floor(diffMs / (1000 * 60));
			const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
			const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

			if (diffMins < 1) return "now";
			if (diffMins < 60) return `${diffMins}m`;
			if (diffHours < 24) return `${diffHours}h`;
			if (diffDays < 7) return `${diffDays}d`;
			return `${Math.floor(diffDays / 7)}w`;
		} catch {
			return "now";
		}
	};

	const getStatusIcon = (item: InboxItem) => {
		// For mentions, show the author's avatar with initials fallback
		if (item.type === "new_mention") {
			const metadata = item.metadata as {
				author_name?: string;
				author_avatar_url?: string | null;
				author_email?: string;
			};
			const authorName = metadata?.author_name;
			const avatarUrl = metadata?.author_avatar_url;
			const authorEmail = metadata?.author_email;

			return (
				<Avatar className="h-8 w-8">
					{avatarUrl && <AvatarImage src={avatarUrl} alt={authorName || "User"} />}
					<AvatarFallback className="text-[10px] bg-primary/10 text-primary">
						{getInitials(authorName, authorEmail)}
					</AvatarFallback>
				</Avatar>
			);
		}

		// For status items (connector/document), show status icons
		const status = item.metadata?.status as string | undefined;

		switch (status) {
			case "in_progress":
				return (
					<div className="h-8 w-8 flex items-center justify-center rounded-full bg-muted">
						<Spinner size="sm" className="text-foreground" />
					</div>
				);
			case "completed":
				return (
					<div className="h-8 w-8 flex items-center justify-center rounded-full bg-green-500/10">
						<CheckCircle2 className="h-4 w-4 text-green-500" />
					</div>
				);
			case "failed":
				return (
					<div className="h-8 w-8 flex items-center justify-center rounded-full bg-red-500/10">
						<AlertCircle className="h-4 w-4 text-red-500" />
					</div>
				);
			default:
				return (
					<div className="h-8 w-8 flex items-center justify-center rounded-full bg-muted">
						<History className="h-4 w-4 text-muted-foreground" />
					</div>
				);
		}
	};

	const getEmptyStateMessage = () => {
		if (activeTab === "mentions") {
			return {
				title: t("no_mentions") || "No mentions",
				hint: t("no_mentions_hint") || "You'll see mentions from others here",
			};
		}
		return {
			title: t("no_status_updates") || "No status updates",
			hint: t("no_status_updates_hint") || "Document and connector updates will appear here",
		};
	};

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
						transition={{ type: "spring", damping: 25, stiffness: 300 }}
						className="fixed inset-y-0 left-0 z-70 w-90 bg-background shadow-xl flex flex-col pointer-events-auto isolate"
						role="dialog"
						aria-modal="true"
						aria-label={t("inbox") || "Inbox"}
					>
						<div className="shrink-0 p-4 pb-2 space-y-3">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Inbox className="h-5 w-5 text-primary" />
									<h2 className="text-lg font-semibold">{t("inbox") || "Inbox"}</h2>
								</div>
								<div className="flex items-center gap-1">
									<DropdownMenu
										open={openDropdown === "filter"}
										onOpenChange={(isOpen) => setOpenDropdown(isOpen ? "filter" : null)}
									>
										<DropdownMenuTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 rounded-full"
											>
												<ListFilter className="h-4 w-4 text-muted-foreground" />
												<span className="sr-only">{t("filter") || "Filter"}</span>
											</Button>
										</DropdownMenuTrigger>
										<DropdownMenuContent align="end" className="w-44 z-80">
											<DropdownMenuLabel className="text-xs text-muted-foreground/80 font-normal">
												{t("filter") || "Filter"}
											</DropdownMenuLabel>
											<DropdownMenuItem
												onClick={() => setActiveFilter("all")}
												className="flex items-center justify-between"
											>
												<span className="flex items-center gap-2">
													<Inbox className="h-4 w-4" />
													<span>{t("unread_and_read") || "Unread & read"}</span>
												</span>
												{activeFilter === "all" && <Check className="h-4 w-4" />}
											</DropdownMenuItem>
											<DropdownMenuItem
												onClick={() => setActiveFilter("unread")}
												className="flex items-center justify-between"
											>
												<span className="flex items-center gap-2">
													<BellDot className="h-4 w-4" />
													<span>{t("unread") || "Unread"}</span>
												</span>
												{activeFilter === "unread" && <Check className="h-4 w-4" />}
											</DropdownMenuItem>
											<DropdownMenuItem
												onClick={() => setActiveFilter("archived")}
												className="flex items-center justify-between"
											>
												<span className="flex items-center gap-2">
													<Archive className="h-4 w-4" />
													<span>{t("archived") || "Archived"}</span>
												</span>
												{activeFilter === "archived" && <Check className="h-4 w-4" />}
											</DropdownMenuItem>
										</DropdownMenuContent>
									</DropdownMenu>
									<DropdownMenu
										open={openDropdown === "options"}
										onOpenChange={(isOpen) => setOpenDropdown(isOpen ? "options" : null)}
									>
										<DropdownMenuTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 rounded-full"
											>
												<MoreHorizontal className="h-4 w-4 text-muted-foreground" />
												<span className="sr-only">{t("more_options") || "More options"}</span>
											</Button>
										</DropdownMenuTrigger>
										<DropdownMenuContent align="end" className="w-40 z-80">
											<DropdownMenuItem
												onClick={handleMarkAllAsRead}
												disabled={unreadCount === 0}
											>
												<CheckCheck className="mr-2 h-4 w-4" />
												<span>{t("mark_all_read") || "Mark all as read"}</span>
											</DropdownMenuItem>
										</DropdownMenuContent>
									</DropdownMenu>
								</div>
							</div>

							<div className="relative">
								<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
								<Input
									type="text"
									placeholder={t("search_inbox") || "Search inbox"}
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

						<Tabs
							value={activeTab}
							onValueChange={(value) => setActiveTab(value as InboxTab)}
							className="shrink-0 mx-4"
						>
							<TabsList className="w-full h-auto p-0 bg-transparent rounded-none border-b">
								<TabsTrigger
									value="mentions"
									className="flex-1 rounded-none border-b-2 border-transparent px-1 py-2 text-xs font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
								>
									<span className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-muted transition-colors">
										<AtSign className="h-4 w-4" />
										<span>{t("mentions") || "Mentions"}</span>
										<span className={cn(
											"inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium",
											unreadMentionsCount === 0 && "invisible"
										)}>
											{unreadMentionsCount || 0}
										</span>
									</span>
								</TabsTrigger>
								<TabsTrigger
									value="status"
									className="flex-1 rounded-none border-b-2 border-transparent px-1 py-2 text-xs font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
								>
									<span className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-muted transition-colors">
										<History className="h-4 w-4" />
										<span>{t("status") || "Status"}</span>
										<span className={cn(
											"inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium",
											unreadStatusCount === 0 && "invisible"
										)}>
											{unreadStatusCount || 0}
										</span>
									</span>
								</TabsTrigger>
							</TabsList>
						</Tabs>

						<div className="flex-1 overflow-y-auto overflow-x-hidden p-2">
							{loading ? (
								<div className="flex items-center justify-center py-8">
									<Spinner size="md" className="text-muted-foreground" />
								</div>
							) : filteredItems.length > 0 ? (
								<div className="space-y-2">
									{filteredItems.map((item) => {
										const isMarkingAsRead = markingAsReadId === item.id;
										const isArchiving = archivingItemId === item.id;
										const isBusy = isMarkingAsRead || isArchiving;
										const isArchived = item.archived === true;

										return (
											<div
												key={item.id}
												className={cn(
													"group flex items-center gap-3 rounded-lg px-3 py-2 text-sm h-[72px] overflow-hidden",
													"hover:bg-accent hover:text-accent-foreground",
													"transition-colors cursor-pointer",
													isBusy && "opacity-50 pointer-events-none"
												)}
											>
												<Tooltip>
													<TooltipTrigger asChild>
														<button
															type="button"
															onClick={() => handleItemClick(item)}
															disabled={isBusy}
															className="flex items-start gap-3 flex-1 min-w-0 text-left overflow-hidden self-start"
														>
															<div className="shrink-0">{getStatusIcon(item)}</div>
															<div className="flex-1 min-w-0 overflow-hidden">
																<p
																	className={cn(
																		"text-xs font-medium line-clamp-2",
																		!item.read && "font-semibold"
																	)}
																>
																	{item.title}
																</p>
																<p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
																	{convertRenderedToDisplay(item.message)}
																</p>
																{/* Mobile action buttons - shown below description on mobile only */}
																<div className="inline-flex items-center gap-0.5 mt-2 md:hidden bg-primary/20 rounded-md px-1 py-0.5">
																	{!item.read && (
																		<Button
																			variant="ghost"
																			size="icon"
																			className="h-6 w-6"
																			onClick={(e) => {
																				e.stopPropagation();
																				handleMarkAsRead(item.id);
																			}}
																			disabled={isBusy}
																		>
																			<CheckCheck className="h-3.5 w-3.5" />
																			<span className="sr-only">{t("mark_as_read") || "Mark as read"}</span>
																		</Button>
																	)}
																	<Button
																		variant="ghost"
																		size="icon"
																		className="h-6 w-6"
																		onClick={(e) => {
																			e.stopPropagation();
																			handleToggleArchive(item.id, isArchived);
																		}}
																		disabled={isArchiving}
																	>
																		{isArchiving ? (
																			<Spinner size="xs" />
																		) : isArchived ? (
																			<RotateCcw className="h-3.5 w-3.5" />
																		) : (
																			<Archive className="h-3.5 w-3.5" />
																		)}
																		<span className="sr-only">{isArchived ? (t("unarchive") || "Restore") : (t("archive") || "Archive")}</span>
																	</Button>
																</div>
															</div>
														</button>
													</TooltipTrigger>
													<TooltipContent side="bottom" align="start" className="max-w-[250px]">
														<p className="font-medium">{item.title}</p>
														<p className="text-muted-foreground mt-1">
															{convertRenderedToDisplay(item.message)}
														</p>
													</TooltipContent>
												</Tooltip>

												{/* Time/dot and 3-dot button container - swap on hover (desktop only) */}
												<div className="relative hidden md:flex items-center shrink-0 w-12 justify-end">
													{/* Time and unread dot - visible by default, hidden on hover or when dropdown is open */}
													<div
														className={cn(
															"flex items-center gap-1.5 transition-opacity duration-150",
															"group-hover:opacity-0 group-hover:pointer-events-none",
															openDropdown === item.id && "opacity-0 pointer-events-none"
														)}
													>
														<span className="text-[10px] text-muted-foreground">
															{formatTime(item.created_at)}
														</span>
														{!item.read && (
															<span className="h-2 w-2 rounded-full bg-blue-500" />
														)}
													</div>

													{/* 3-dot menu - hidden by default, visible on hover or when dropdown is open */}
													<DropdownMenu
														open={openDropdown === item.id}
														onOpenChange={(isOpen) =>
															setOpenDropdown(isOpen ? item.id : null)
														}
													>
														<DropdownMenuTrigger asChild>
															<Button
																variant="ghost"
																size="icon"
																className={cn(
																	"h-6 w-6 absolute right-0 transition-opacity duration-150",
																	"opacity-0 pointer-events-none",
																	"group-hover:opacity-100 group-hover:pointer-events-auto",
																	openDropdown === item.id && "!opacity-100 !pointer-events-auto"
																)}
																disabled={isBusy}
															>
															{isArchiving ? (
																<Spinner size="xs" />
															) : (
																<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
															)}
															<span className="sr-only">
																{t("more_options") || "More options"}
															</span>
														</Button>
													</DropdownMenuTrigger>
													<DropdownMenuContent align="end" className="w-40 z-80">
														{!item.read && (
															<>
																<DropdownMenuItem
																	onClick={() => handleMarkAsRead(item.id)}
																	disabled={isBusy}
																>
																	<CheckCheck className="mr-2 h-4 w-4" />
																	<span>{t("mark_as_read") || "Mark as read"}</span>
																</DropdownMenuItem>
																<DropdownMenuSeparator />
															</>
														)}
														<DropdownMenuItem
															onClick={() => handleToggleArchive(item.id, isArchived)}
															disabled={isArchiving}
														>
															{isArchived ? (
																<>
																	<RotateCcw className="mr-2 h-4 w-4" />
																	<span>{t("unarchive") || "Restore"}</span>
																</>
															) : (
																<>
																	<Archive className="mr-2 h-4 w-4" />
																	<span>{t("archive") || "Archive"}</span>
																</>
															)}
														</DropdownMenuItem>
													</DropdownMenuContent>
												</DropdownMenu>
												</div>

												{/* Mobile time and unread dot - always visible on mobile */}
												<div className="flex md:hidden items-center gap-1.5 shrink-0">
													<span className="text-[10px] text-muted-foreground">
														{formatTime(item.created_at)}
													</span>
													{!item.read && (
														<span className="h-2 w-2 rounded-full bg-blue-500" />
													)}
												</div>
											</div>
										);
									})}
								</div>
							) : searchQuery ? (
								<div className="text-center py-8">
									<Search className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
									<p className="text-sm text-muted-foreground">
										{t("no_results_found") || "No results found"}
									</p>
									<p className="text-xs text-muted-foreground/70 mt-1">
										{t("try_different_search") || "Try a different search term"}
									</p>
								</div>
							) : (
								<div className="text-center py-8">
									{activeTab === "mentions" ? (
										<AtSign className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
									) : (
										<History className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
									)}
									<p className="text-sm text-muted-foreground">
										{getEmptyStateMessage().title}
									</p>
									<p className="text-xs text-muted-foreground/70 mt-1">
										{getEmptyStateMessage().hint}
									</p>
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
