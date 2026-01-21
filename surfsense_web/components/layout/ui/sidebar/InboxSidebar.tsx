"use client";

import {
	AlertCircle,
	AtSign,
	BellDot,
	Check,
	CheckCheck,
	CheckCircle2,
	History,
	Inbox,
	ListFilter,
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
type InboxFilter = "all" | "unread";

interface InboxSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	inboxItems: InboxItem[];
	unreadCount: number;
	loading: boolean;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
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
	onCloseMobileSidebar,
}: InboxSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();

	const [searchQuery, setSearchQuery] = useState("");
	const [activeTab, setActiveTab] = useState<InboxTab>("mentions");
	const [activeFilter, setActiveFilter] = useState<InboxFilter>("all");
	const [mounted, setMounted] = useState(false);
	// Dropdown state for filter menu
	const [openDropdown, setOpenDropdown] = useState<"filter" | null>(null);
	const [markingAsReadId, setMarkingAsReadId] = useState<number | null>(null);

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
		if (activeFilter === "unread") {
			items = items.filter((item) => !item.read);
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

	// Count unread items per tab
	const unreadMentionsCount = useMemo(() => {
		return mentionItems.filter((item) => !item.read).length;
	}, [mentionItems]);

	const unreadStatusCount = useMemo(() => {
		return statusItems.filter((item) => !item.read).length;
	}, [statusItems]);

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

	const handleMarkAllAsRead = useCallback(async () => {
		await markAllAsRead();
	}, [markAllAsRead]);

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
										<Tooltip>
											<TooltipTrigger asChild>
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
											</TooltipTrigger>
											<TooltipContent className="z-80">
												{t("filter") || "Filter"}
											</TooltipContent>
										</Tooltip>
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
													<span>{t("all") || "All"}</span>
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
										</DropdownMenuContent>
									</DropdownMenu>
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 rounded-full"
												onClick={handleMarkAllAsRead}
												disabled={unreadCount === 0}
											>
												<CheckCheck className="h-4 w-4 text-muted-foreground" />
												<span className="sr-only">{t("mark_all_read") || "Mark all as read"}</span>
											</Button>
										</TooltipTrigger>
										<TooltipContent className="z-80">
											{t("mark_all_read") || "Mark all as read"}
										</TooltipContent>
									</Tooltip>
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
										<span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium">
											{unreadMentionsCount}
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
										<span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium">
											{unreadStatusCount}
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

										return (
											<div
												key={item.id}
												className={cn(
													"group flex items-center gap-3 rounded-lg px-3 py-3 text-sm h-[80px] overflow-hidden",
													"hover:bg-accent hover:text-accent-foreground",
													"transition-colors cursor-pointer",
													isMarkingAsRead && "opacity-50 pointer-events-none"
												)}
											>
												<Tooltip>
													<TooltipTrigger asChild>
														<button
															type="button"
															onClick={() => handleItemClick(item)}
															disabled={isMarkingAsRead}
															className="flex items-center gap-3 flex-1 min-w-0 text-left overflow-hidden"
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

												{/* Time and unread dot - fixed width to prevent content shift */}
												<div className="flex items-center justify-end gap-1.5 shrink-0 w-10">
													<span className="text-[10px] text-muted-foreground">
														{formatTime(item.created_at)}
													</span>
													{!item.read && (
														<span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />
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
