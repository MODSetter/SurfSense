"use client";

import { useAtom } from "jotai";
import {
	AlertCircle,
	AlertTriangle,
	AtSign,
	BellDot,
	Check,
	CheckCheck,
	CheckCircle2,
	ChevronLeft,
	ChevronRight,
	History,
	Inbox,
	LayoutGrid,
	ListFilter,
	Search,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { setCommentsCollapsedAtom, setTargetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { convertRenderedToDisplay } from "@/components/chat-comments/comment-item/comment-item";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
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
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	isConnectorIndexingMetadata,
	isNewMentionMetadata,
	isPageLimitExceededMetadata,
} from "@/contracts/types/inbox.types";
import type { InboxItem } from "@/hooks/use-inbox";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";
import { useSidebarContextSafe } from "../../hooks";

// Sidebar width constants
const SIDEBAR_COLLAPSED_WIDTH = 60;
const SIDEBAR_EXPANDED_WIDTH = 240;

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

/**
 * Format count for display: shows numbers up to 999, then "1k+", "2k+", etc.
 */
function formatInboxCount(count: number): string {
	if (count <= 999) {
		return count.toString();
	}
	const thousands = Math.floor(count / 1000);
	return `${thousands}k+`;
}

/**
 * Get display name for connector type
 */
function getConnectorTypeDisplayName(connectorType: string): string {
	const displayNames: Record<string, string> = {
		GITHUB_CONNECTOR: "GitHub",
		GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		GOOGLE_GMAIL_CONNECTOR: "Gmail",
		GOOGLE_DRIVE_CONNECTOR: "Google Drive",
		COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Composio Google Drive",
		COMPOSIO_GMAIL_CONNECTOR: "Composio Gmail",
		COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Composio Google Calendar",
		LINEAR_CONNECTOR: "Linear",
		NOTION_CONNECTOR: "Notion",
		SLACK_CONNECTOR: "Slack",
		TEAMS_CONNECTOR: "Microsoft Teams",
		DISCORD_CONNECTOR: "Discord",
		JIRA_CONNECTOR: "Jira",
		CONFLUENCE_CONNECTOR: "Confluence",
		BOOKSTACK_CONNECTOR: "BookStack",
		CLICKUP_CONNECTOR: "ClickUp",
		AIRTABLE_CONNECTOR: "Airtable",
		LUMA_CONNECTOR: "Luma",
		ELASTICSEARCH_CONNECTOR: "Elasticsearch",
		WEBCRAWLER_CONNECTOR: "Web Crawler",
		YOUTUBE_CONNECTOR: "YouTube",
		CIRCLEBACK_CONNECTOR: "Circleback",
		MCP_CONNECTOR: "MCP",
		OBSIDIAN_CONNECTOR: "Obsidian",
		TAVILY_API: "Tavily",
		SEARXNG_API: "SearXNG",
		LINKUP_API: "Linkup",
		BAIDU_SEARCH_API: "Baidu",
	};

	return (
		displayNames[connectorType] ||
		connectorType
			.replace(/_/g, " ")
			.replace(/CONNECTOR|API/gi, "")
			.trim()
	);
}

type InboxTab = "mentions" | "status";
type InboxFilter = "all" | "unread";

// Tab-specific data source with independent pagination
interface TabDataSource {
	items: InboxItem[];
	unreadCount: number;
	loading: boolean;
	loadingMore?: boolean;
	hasMore?: boolean;
	loadMore?: () => void;
}

interface InboxSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Mentions tab data source with independent pagination */
	mentions: TabDataSource;
	/** Status tab data source with independent pagination */
	status: TabDataSource;
	/** Combined unread count for mark all as read */
	totalUnreadCount: number;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
	onCloseMobileSidebar?: () => void;
	/** Whether the inbox is docked (permanent) or floating */
	isDocked?: boolean;
	/** Callback to toggle docked state */
	onDockedChange?: (docked: boolean) => void;
}

export function InboxSidebar({
	open,
	onOpenChange,
	mentions,
	status,
	totalUnreadCount,
	markAsRead,
	markAllAsRead,
	onCloseMobileSidebar,
	isDocked = false,
	onDockedChange,
}: InboxSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const isMobile = !useMediaQuery("(min-width: 640px)");

	// Comments collapsed state (desktop only, when docked)
	const [, setCommentsCollapsed] = useAtom(setCommentsCollapsedAtom);
	// Target comment for navigation - also ensures comments panel is visible
	const [, setTargetCommentId] = useAtom(setTargetCommentIdAtom);

	const [searchQuery, setSearchQuery] = useState("");
	const [activeTab, setActiveTab] = useState<InboxTab>("mentions");
	const [activeFilter, setActiveFilter] = useState<InboxFilter>("all");
	const [selectedConnector, setSelectedConnector] = useState<string | null>(null);
	const [mounted, setMounted] = useState(false);
	// Dropdown state for filter menu (desktop only)
	const [openDropdown, setOpenDropdown] = useState<"filter" | null>(null);
	// Drawer state for filter menu (mobile only)
	const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
	const [markingAsReadId, setMarkingAsReadId] = useState<number | null>(null);

	// Prefetch trigger ref - placed on item near the end
	const prefetchTriggerRef = useRef<HTMLDivElement>(null);

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

	// Only lock body scroll on mobile when inbox is open
	useEffect(() => {
		if (!open || !isMobile) return;

		// Store original overflow to restore on cleanup
		const originalOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";

		return () => {
			document.body.style.overflow = originalOverflow;
		};
	}, [open, isMobile]);

	// Reset connector filter when switching away from status tab
	useEffect(() => {
		if (activeTab !== "status") {
			setSelectedConnector(null);
		}
	}, [activeTab]);

	// Get current tab's data source - each tab has independent data and pagination
	const currentDataSource = activeTab === "mentions" ? mentions : status;
	const { loading, loadingMore = false, hasMore = false, loadMore } = currentDataSource;

	// Status tab includes: connector indexing, document processing, page limit exceeded, connector deletion
	// Filter to only show status notification types
	const statusItems = useMemo(
		() =>
			status.items.filter(
				(item) =>
					item.type === "connector_indexing" ||
					item.type === "document_processing" ||
					item.type === "page_limit_exceeded" ||
					item.type === "connector_deletion"
			),
		[status.items]
	);

	// Get unique connector types from status items for filtering
	const uniqueConnectorTypes = useMemo(() => {
		const connectorTypes = new Set<string>();

		statusItems
			.filter((item) => item.type === "connector_indexing")
			.forEach((item) => {
				// Use type guard for safe metadata access
				if (isConnectorIndexingMetadata(item.metadata)) {
					connectorTypes.add(item.metadata.connector_type);
				}
			});

		return Array.from(connectorTypes).map((type) => ({
			type,
			displayName: getConnectorTypeDisplayName(type),
		}));
	}, [statusItems]);

	// Get items for current tab - mentions use their source directly, status uses filtered items
	const displayItems = activeTab === "mentions" ? mentions.items : statusItems;

	// Filter items based on filter type, connector filter, and search query
	const filteredItems = useMemo(() => {
		let items = displayItems;

		// Apply read/unread filter
		if (activeFilter === "unread") {
			items = items.filter((item) => !item.read);
		}

		// Apply connector filter (only for status tab)
		if (activeTab === "status" && selectedConnector) {
			items = items.filter((item) => {
				if (item.type === "connector_indexing") {
					// Use type guard for safe metadata access
					if (isConnectorIndexingMetadata(item.metadata)) {
						return item.metadata.connector_type === selectedConnector;
					}
					return false;
				}
				return false; // Hide document_processing when a specific connector is selected
			});
		}

		// Apply search query
		if (searchQuery.trim()) {
			const query = searchQuery.toLowerCase();
			items = items.filter(
				(item) =>
					item.title.toLowerCase().includes(query) || item.message.toLowerCase().includes(query)
			);
		}

		return items;
	}, [displayItems, activeFilter, activeTab, selectedConnector, searchQuery]);

	// Intersection Observer for infinite scroll with prefetching
	// Only active when not searching (search results are client-side filtered)
	useEffect(() => {
		if (!loadMore || !hasMore || loadingMore || !open || searchQuery.trim()) return;

		const observer = new IntersectionObserver(
			(entries) => {
				// When trigger element is visible, load more
				if (entries[0]?.isIntersecting) {
					loadMore();
				}
			},
			{
				root: null, // viewport
				rootMargin: "100px", // Start loading 100px before visible
				threshold: 0,
			}
		);

		if (prefetchTriggerRef.current) {
			observer.observe(prefetchTriggerRef.current);
		}

		return () => observer.disconnect();
	}, [loadMore, hasMore, loadingMore, open, searchQuery]);

	// Use unread counts from data sources (more accurate than client-side counting)
	const unreadMentionsCount = mentions.unreadCount;
	const unreadStatusCount = status.unreadCount;

	const handleItemClick = useCallback(
		async (item: InboxItem) => {
			if (!item.read) {
				setMarkingAsReadId(item.id);
				await markAsRead(item.id);
				setMarkingAsReadId(null);
			}

			if (item.type === "new_mention") {
				// Use type guard for safe metadata access
				if (isNewMentionMetadata(item.metadata)) {
					const searchSpaceId = item.search_space_id;
					const threadId = item.metadata.thread_id;
					const commentId = item.metadata.comment_id;

					if (searchSpaceId && threadId) {
						// Pre-set target comment ID before navigation
						// This also ensures comments panel is not collapsed
						if (commentId) {
							setTargetCommentId(commentId);
						}

						const url = commentId
							? `/dashboard/${searchSpaceId}/new-chat/${threadId}?commentId=${commentId}`
							: `/dashboard/${searchSpaceId}/new-chat/${threadId}`;
						onOpenChange(false);
						onCloseMobileSidebar?.();
						router.push(url);
					}
				}
			} else if (item.type === "page_limit_exceeded") {
				// Navigate to the upgrade/more-pages page
				if (isPageLimitExceededMetadata(item.metadata)) {
					const actionUrl = item.metadata.action_url;
					if (actionUrl) {
						onOpenChange(false);
						onCloseMobileSidebar?.();
						router.push(actionUrl);
					}
				}
			}
		},
		[markAsRead, router, onOpenChange, onCloseMobileSidebar, setTargetCommentId]
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
			// Use type guard for safe metadata access
			if (isNewMentionMetadata(item.metadata)) {
				const authorName = item.metadata.author_name;
				const avatarUrl = item.metadata.author_avatar_url;
				const authorEmail = item.metadata.author_email;

				return (
					<Avatar className="h-8 w-8">
						{avatarUrl && <AvatarImage src={avatarUrl} alt={authorName || "User"} />}
						<AvatarFallback className="text-[10px] bg-primary/10 text-primary">
							{getInitials(authorName, authorEmail)}
						</AvatarFallback>
					</Avatar>
				);
			}
			// Fallback for invalid metadata
			return (
				<Avatar className="h-8 w-8">
					<AvatarFallback className="text-[10px] bg-primary/10 text-primary">
						{getInitials(null, null)}
					</AvatarFallback>
				</Avatar>
			);
		}

		// For page limit exceeded, show a warning icon with amber/orange color
		if (item.type === "page_limit_exceeded") {
			return (
				<div className="h-8 w-8 flex items-center justify-center rounded-full bg-amber-500/10">
					<AlertTriangle className="h-4 w-4 text-amber-500" />
				</div>
			);
		}

		// For status items (connector/document), show status icons
		// Safely access status from metadata
		const metadata = item.metadata as Record<string, unknown>;
		const status = typeof metadata?.status === "string" ? metadata.status : undefined;

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

	// Get sidebar collapsed state from context (provided by LayoutShell)
	const sidebarContext = useSidebarContextSafe();
	const isCollapsed = sidebarContext?.isCollapsed ?? false;

	// Calculate the left position for the inbox panel (relative to sidebar)
	const sidebarWidth = isCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH;

	if (!mounted) return null;

	// Shared content component for both docked and floating modes
	const inboxContent = (
		<>
			<div className="shrink-0 p-4 pb-2 space-y-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<h2 className="text-lg font-semibold">{t("inbox") || "Inbox"}</h2>
					</div>
					<div className="flex items-center gap-1">
						{/* Mobile: Button that opens bottom drawer */}
						{isMobile ? (
							<>
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											className="h-8 w-8 rounded-full"
											onClick={() => setFilterDrawerOpen(true)}
										>
											<ListFilter className="h-4 w-4 text-muted-foreground" />
											<span className="sr-only">{t("filter") || "Filter"}</span>
										</Button>
									</TooltipTrigger>
									<TooltipContent className="z-80">{t("filter") || "Filter"}</TooltipContent>
								</Tooltip>
								<Drawer
									open={filterDrawerOpen}
									onOpenChange={setFilterDrawerOpen}
									shouldScaleBackground={false}
								>
									<DrawerContent className="max-h-[70vh] z-80" overlayClassName="z-80">
										<DrawerHandle />
										<DrawerHeader className="px-4 pb-3 pt-2">
											<DrawerTitle className="flex items-center gap-2 text-base font-semibold">
												<ListFilter className="size-5" />
												{t("filter") || "Filter"}
											</DrawerTitle>
										</DrawerHeader>
										<div className="flex-1 overflow-y-auto p-4 space-y-4">
											{/* Filter section */}
											<div className="space-y-2">
												<p className="text-xs text-muted-foreground/80 font-medium px-1">
													{t("filter") || "Filter"}
												</p>
												<div className="space-y-1">
													<button
														type="button"
														onClick={() => {
															setActiveFilter("all");
															setFilterDrawerOpen(false);
														}}
														className={cn(
															"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
															activeFilter === "all"
																? "bg-primary/10 text-primary"
																: "hover:bg-muted"
														)}
													>
														<span className="flex items-center gap-2">
															<Inbox className="h-4 w-4" />
															<span>{t("all") || "All"}</span>
														</span>
														{activeFilter === "all" && <Check className="h-4 w-4" />}
													</button>
													<button
														type="button"
														onClick={() => {
															setActiveFilter("unread");
															setFilterDrawerOpen(false);
														}}
														className={cn(
															"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
															activeFilter === "unread"
																? "bg-primary/10 text-primary"
																: "hover:bg-muted"
														)}
													>
														<span className="flex items-center gap-2">
															<BellDot className="h-4 w-4" />
															<span>{t("unread") || "Unread"}</span>
														</span>
														{activeFilter === "unread" && <Check className="h-4 w-4" />}
													</button>
												</div>
											</div>
											{/* Connectors section - only for status tab */}
											{activeTab === "status" && uniqueConnectorTypes.length > 0 && (
												<div className="space-y-2">
													<p className="text-xs text-muted-foreground/80 font-medium px-1">
														{t("connectors") || "Connectors"}
													</p>
													<div className="space-y-1">
														<button
															type="button"
															onClick={() => {
																setSelectedConnector(null);
																setFilterDrawerOpen(false);
															}}
															className={cn(
																"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
																selectedConnector === null
																	? "bg-primary/10 text-primary"
																	: "hover:bg-muted"
															)}
														>
															<span className="flex items-center gap-2">
																<LayoutGrid className="h-4 w-4" />
																<span>{t("all_connectors") || "All connectors"}</span>
															</span>
															{selectedConnector === null && <Check className="h-4 w-4" />}
														</button>
														{uniqueConnectorTypes.map((connector) => (
															<button
																key={connector.type}
																type="button"
																onClick={() => {
																	setSelectedConnector(connector.type);
																	setFilterDrawerOpen(false);
																}}
																className={cn(
																	"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
																	selectedConnector === connector.type
																		? "bg-primary/10 text-primary"
																		: "hover:bg-muted"
																)}
															>
																<span className="flex items-center gap-2">
																	{getConnectorIcon(connector.type, "h-4 w-4")}
																	<span>{connector.displayName}</span>
																</span>
																{selectedConnector === connector.type && (
																	<Check className="h-4 w-4" />
																)}
															</button>
														))}
													</div>
												</div>
											)}
										</div>
									</DrawerContent>
								</Drawer>
							</>
						) : (
							/* Desktop: Dropdown menu */
							<DropdownMenu
								open={openDropdown === "filter"}
								onOpenChange={(isOpen) => setOpenDropdown(isOpen ? "filter" : null)}
							>
								<Tooltip>
									<TooltipTrigger asChild>
										<DropdownMenuTrigger asChild>
											<Button variant="ghost" size="icon" className="h-8 w-8 rounded-full">
												<ListFilter className="h-4 w-4 text-muted-foreground" />
												<span className="sr-only">{t("filter") || "Filter"}</span>
											</Button>
										</DropdownMenuTrigger>
									</TooltipTrigger>
									<TooltipContent className="z-80">{t("filter") || "Filter"}</TooltipContent>
								</Tooltip>
								<DropdownMenuContent
									align="end"
									className={cn("z-80", activeTab === "status" ? "w-52" : "w-44")}
								>
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
									{activeTab === "status" && uniqueConnectorTypes.length > 0 && (
										<>
											<DropdownMenuLabel className="text-xs text-muted-foreground/80 font-normal mt-2">
												{t("connectors") || "Connectors"}
											</DropdownMenuLabel>
											<DropdownMenuItem
												onClick={() => setSelectedConnector(null)}
												className="flex items-center justify-between"
											>
												<span className="flex items-center gap-2">
													<LayoutGrid className="h-4 w-4" />
													<span>{t("all_connectors") || "All connectors"}</span>
												</span>
												{selectedConnector === null && <Check className="h-4 w-4" />}
											</DropdownMenuItem>
											{uniqueConnectorTypes.map((connector) => (
												<DropdownMenuItem
													key={connector.type}
													onClick={() => setSelectedConnector(connector.type)}
													className="flex items-center justify-between"
												>
													<span className="flex items-center gap-2">
														{getConnectorIcon(connector.type, "h-4 w-4")}
														<span>{connector.displayName}</span>
													</span>
													{selectedConnector === connector.type && <Check className="h-4 w-4" />}
												</DropdownMenuItem>
											))}
										</>
									)}
								</DropdownMenuContent>
							</DropdownMenu>
						)}
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="h-8 w-8 rounded-full"
									onClick={handleMarkAllAsRead}
									disabled={totalUnreadCount === 0}
								>
									<CheckCheck className="h-4 w-4 text-muted-foreground" />
									<span className="sr-only">{t("mark_all_read") || "Mark all as read"}</span>
								</Button>
							</TooltipTrigger>
							<TooltipContent className="z-80">
								{t("mark_all_read") || "Mark all as read"}
							</TooltipContent>
						</Tooltip>
						{/* Close button - mobile only */}
						{isMobile && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-8 w-8 rounded-full"
										onClick={() => onOpenChange(false)}
									>
										<ChevronLeft className="h-4 w-4 text-muted-foreground" />
										<span className="sr-only">{t("close") || "Close"}</span>
									</Button>
								</TooltipTrigger>
								<TooltipContent className="z-80">{t("close") || "Close"}</TooltipContent>
							</Tooltip>
						)}
						{/* Dock/Undock button - desktop only */}
						{!isMobile && onDockedChange && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-8 w-8 rounded-full"
										onClick={() => {
											if (isDocked) {
												// Collapse: show comments immediately, then close inbox
												setCommentsCollapsed(false);
												onDockedChange(false);
												onOpenChange(false);
											} else {
												// Expand: hide comments immediately
												setCommentsCollapsed(true);
												onDockedChange(true);
											}
										}}
									>
										{isDocked ? (
											<ChevronLeft className="h-4 w-4 text-muted-foreground" />
										) : (
											<ChevronRight className="h-4 w-4 text-muted-foreground" />
										)}
										<span className="sr-only">{isDocked ? "Collapse panel" : "Expand panel"}</span>
									</Button>
								</TooltipTrigger>
								<TooltipContent className="z-80">
									{isDocked ? "Collapse panel" : "Expand panel"}
								</TooltipContent>
							</Tooltip>
						)}
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
								{formatInboxCount(unreadMentionsCount)}
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
								{formatInboxCount(unreadStatusCount)}
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
						{filteredItems.map((item, index) => {
							const isMarkingAsRead = markingAsReadId === item.id;
							// Place prefetch trigger on 5th item from end (only if not searching)
							const isPrefetchTrigger =
								!searchQuery && hasMore && index === filteredItems.length - 5;

							return (
								<div
									key={item.id}
									ref={isPrefetchTrigger ? prefetchTriggerRef : undefined}
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
										{!item.read && <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />}
									</div>
								</div>
							);
						})}
						{/* Fallback trigger at the very end if less than 5 items and not searching */}
						{!searchQuery && filteredItems.length < 5 && hasMore && (
							<div ref={prefetchTriggerRef} className="h-1" />
						)}
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
						<p className="text-sm text-muted-foreground">{getEmptyStateMessage().title}</p>
						<p className="text-xs text-muted-foreground/70 mt-1">{getEmptyStateMessage().hint}</p>
					</div>
				)}
			</div>
		</>
	);

	// DOCKED MODE: Render as a static flex child (no animation, no click-away)
	if (isDocked && open && !isMobile) {
		return (
			<aside
				className="h-full w-[360px] shrink-0 bg-background flex flex-col border-r"
				aria-label={t("inbox") || "Inbox"}
			>
				{inboxContent}
			</aside>
		);
	}

	// FLOATING MODE: Render with animation and click-away layer
	return (
		<AnimatePresence>
			{open && (
				<>
					{/* Click-away layer - only covers the content area, not the sidebar */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.15 }}
						style={{
							left: isMobile ? 0 : sidebarWidth,
						}}
						className="absolute inset-y-0 right-0"
						onClick={() => onOpenChange(false)}
						aria-hidden="true"
					/>

					{/* Clip container - positioned at sidebar edge with overflow hidden */}
					<div
						style={{
							left: isMobile ? 0 : sidebarWidth,
							width: isMobile ? "100%" : 360,
						}}
						className={cn("absolute z-10 overflow-hidden pointer-events-none", "inset-y-0")}
					>
						<motion.div
							initial={{ x: "-100%" }}
							animate={{ x: 0 }}
							exit={{ x: "-100%" }}
							transition={{ type: "tween", duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
							className={cn(
								"h-full w-full bg-background flex flex-col pointer-events-auto",
								"sm:border-r sm:shadow-xl"
							)}
							role="dialog"
							aria-modal="true"
							aria-label={t("inbox") || "Inbox"}
						>
							{inboxContent}
						</motion.div>
					</div>
				</>
			)}
		</AnimatePresence>
	);
}
