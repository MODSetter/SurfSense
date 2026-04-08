"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtom } from "jotai";
import {
	AlertCircle,
	AlertTriangle,
	BellDot,
	Check,
	CheckCheck,
	CheckCircle2,
	ChevronLeft,
	History,
	Inbox,
	LayoutGrid,
	ListFilter,
	MessageSquare,
	Search,
	X,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { setTargetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { convertRenderedToDisplay } from "@/components/chat-comments/comment-item/comment-item";
import { getDocumentTypeLabel } from "@/components/documents/DocumentTypeIcon";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/animated-tabs";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	isCommentReplyMetadata,
	isConnectorIndexingMetadata,
	isDocumentProcessingMetadata,
	isNewMentionMetadata,
	isPageLimitExceededMetadata,
} from "@/contracts/types/inbox.types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import type { InboxItem } from "@/hooks/use-inbox";
import { useMediaQuery } from "@/hooks/use-media-query";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

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

function formatInboxCount(count: number): string {
	if (count <= 999) {
		return count.toString();
	}
	const thousands = Math.floor(count / 1000);
	return `${thousands}k+`;
}

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
		ONEDRIVE_CONNECTOR: "OneDrive",
		DROPBOX_CONNECTOR: "Dropbox",
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

type InboxTab = "comments" | "status";
type InboxFilter = "all" | "unread" | "errors";

interface TabDataSource {
	items: InboxItem[];
	unreadCount: number;
	loading: boolean;
	loadingMore: boolean;
	hasMore: boolean;
	loadMore: () => void;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
}

export interface InboxSidebarContentProps {
	onOpenChange: (open: boolean) => void;
	comments: TabDataSource;
	status: TabDataSource;
	totalUnreadCount: number;
	onCloseMobileSidebar?: () => void;
}

interface InboxSidebarProps extends InboxSidebarContentProps {
	open: boolean;
}

export function InboxSidebarContent({
	onOpenChange,
	comments,
	status,
	totalUnreadCount,
	onCloseMobileSidebar,
}: InboxSidebarContentProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const isMobile = !useMediaQuery("(min-width: 640px)");
	const searchSpaceId = params?.search_space_id ? Number(params.search_space_id) : null;

	const [, setTargetCommentId] = useAtom(setTargetCommentIdAtom);

	const [searchQuery, setSearchQuery] = useState("");
	const debouncedSearch = useDebouncedValue(searchQuery, 300);
	const isSearchMode = !!debouncedSearch.trim();
	const [activeTab, setActiveTab] = useState<InboxTab>("comments");
	const [activeFilter, setActiveFilter] = useState<InboxFilter>("all");
	const [selectedSource, setSelectedSource] = useState<string | null>(null);
	const [mounted, setMounted] = useState(false);
	const [openDropdown, setOpenDropdown] = useState<"filter" | null>(null);
	const [connectorScrollPos, setConnectorScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const connectorRafRef = useRef<number>();
	const handleConnectorScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		if (connectorRafRef.current) return;
		connectorRafRef.current = requestAnimationFrame(() => {
			const atTop = el.scrollTop <= 2;
			const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
			setConnectorScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
			connectorRafRef.current = undefined;
		});
	}, []);
	useEffect(
		() => () => {
			if (connectorRafRef.current) cancelAnimationFrame(connectorRafRef.current);
		},
		[]
	);
	const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
	const [markingAsReadId, setMarkingAsReadId] = useState<number | null>(null);

	const prefetchTriggerRef = useRef<HTMLDivElement>(null);

	// Server-side search query
	const searchTypeFilter = activeTab === "comments" ? ("new_mention" as const) : undefined;
	const { data: searchResponse, isLoading: isSearchLoading } = useQuery({
		queryKey: cacheKeys.notifications.search(searchSpaceId, debouncedSearch.trim(), activeTab),
		queryFn: () =>
			notificationsApiService.getNotifications({
				queryParams: {
					search_space_id: searchSpaceId ?? undefined,
					type: searchTypeFilter,
					search: debouncedSearch.trim(),
					limit: 50,
				},
			}),
		staleTime: 30 * 1000,
		enabled: isSearchMode,
	});

	useEffect(() => {
		setMounted(true);
	}, []);

	useEffect(() => {
		if (!isMobile) return;
		const originalOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = originalOverflow;
		};
	}, [isMobile]);

	useEffect(() => {
		if (activeTab !== "status") {
			setSelectedSource(null);
		}
	}, [activeTab]);

	// Active tab's data source — fully independent loading, pagination, and counts
	const activeSource = activeTab === "comments" ? comments : status;

	// Fetch source types for the status tab filter
	const { data: sourceTypesData } = useQuery({
		queryKey: cacheKeys.notifications.sourceTypes(searchSpaceId),
		queryFn: () => notificationsApiService.getSourceTypes(searchSpaceId ?? undefined),
		staleTime: 60 * 1000,
		enabled: activeTab === "status",
	});

	const statusSourceOptions = useMemo(() => {
		if (!sourceTypesData?.sources) return [];

		return sourceTypesData.sources.map((source) => ({
			key: source.key,
			type: source.type,
			category: source.category,
			displayName:
				source.category === "connector"
					? getConnectorTypeDisplayName(source.type)
					: getDocumentTypeLabel(source.type),
		}));
	}, [sourceTypesData]);

	// Client-side filter: source type
	const matchesSourceFilter = useCallback(
		(item: InboxItem): boolean => {
			if (!selectedSource) return true;
			if (selectedSource.startsWith("connector:")) {
				const connectorType = selectedSource.slice("connector:".length);
				return (
					item.type === "connector_indexing" &&
					isConnectorIndexingMetadata(item.metadata) &&
					item.metadata.connector_type === connectorType
				);
			}
			if (selectedSource.startsWith("doctype:")) {
				const docType = selectedSource.slice("doctype:".length);
				return (
					item.type === "document_processing" &&
					isDocumentProcessingMetadata(item.metadata) &&
					item.metadata.document_type === docType
				);
			}
			return true;
		},
		[selectedSource]
	);

	// Client-side filter: unread / errors
	const matchesActiveFilter = useCallback(
		(item: InboxItem): boolean => {
			if (activeFilter === "unread") return !item.read;
			if (activeFilter === "errors") {
				if (item.type === "page_limit_exceeded") return true;
				const meta = item.metadata as Record<string, unknown> | undefined;
				return typeof meta?.status === "string" && meta.status === "failed";
			}
			return true;
		},
		[activeFilter]
	);

	// Defer non-urgent list updates so the search input stays responsive.
	// The deferred snapshot lags one render behind the live value intentionally.
	const deferredTabItems = useDeferredValue(activeSource.items);
	const deferredSearchItems = useDeferredValue(searchResponse?.items ?? []);

	// Two data paths: search mode (API) or default (per-tab data source)
	const filteredItems = useMemo(() => {
		const tabItems: InboxItem[] = isSearchMode ? deferredSearchItems : deferredTabItems;

		let result = tabItems;
		if (activeFilter !== "all") {
			result = result.filter(matchesActiveFilter);
		}
		if (activeTab === "status" && selectedSource) {
			result = result.filter(matchesSourceFilter);
		}

		return result;
	}, [
		isSearchMode,
		deferredSearchItems,
		deferredTabItems,
		activeTab,
		activeFilter,
		selectedSource,
		matchesActiveFilter,
		matchesSourceFilter,
	]);

	// Infinite scroll — uses active tab's pagination
	useEffect(() => {
		if (!activeSource.hasMore || activeSource.loadingMore || isSearchMode) return;

		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					activeSource.loadMore();
				}
			},
			{
				root: null,
				rootMargin: "100px",
				threshold: 0,
			}
		);

		if (prefetchTriggerRef.current) {
			observer.observe(prefetchTriggerRef.current);
		}

		return () => observer.disconnect();
	}, [activeSource.hasMore, activeSource.loadingMore, activeSource.loadMore, isSearchMode]);

	const handleItemClick = useCallback(
		async (item: InboxItem) => {
			if (!item.read) {
				setMarkingAsReadId(item.id);
				await activeSource.markAsRead(item.id);
				setMarkingAsReadId(null);
			}

			if (item.type === "new_mention") {
				if (isNewMentionMetadata(item.metadata)) {
					const searchSpaceId = item.search_space_id;
					const threadId = item.metadata.thread_id;
					const commentId = item.metadata.comment_id;

					if (searchSpaceId && threadId) {
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
			} else if (item.type === "comment_reply") {
				if (isCommentReplyMetadata(item.metadata)) {
					const searchSpaceId = item.search_space_id;
					const threadId = item.metadata.thread_id;
					const replyId = item.metadata.reply_id;

					if (searchSpaceId && threadId) {
						if (replyId) {
							setTargetCommentId(replyId);
						}
						const url = replyId
							? `/dashboard/${searchSpaceId}/new-chat/${threadId}?commentId=${replyId}`
							: `/dashboard/${searchSpaceId}/new-chat/${threadId}`;
						onOpenChange(false);
						onCloseMobileSidebar?.();
						router.push(url);
					}
				}
			} else if (item.type === "page_limit_exceeded") {
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
		[activeSource.markAsRead, router, onOpenChange, onCloseMobileSidebar, setTargetCommentId]
	);

	const handleMarkAllAsRead = useCallback(async () => {
		await Promise.all([comments.markAllAsRead(), status.markAllAsRead()]);
	}, [comments.markAllAsRead, status.markAllAsRead]);

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
		if (item.type === "new_mention" || item.type === "comment_reply") {
			const metadata =
				item.type === "new_mention"
					? isNewMentionMetadata(item.metadata)
						? item.metadata
						: null
					: isCommentReplyMetadata(item.metadata)
						? item.metadata
						: null;

			if (metadata) {
				return (
					<Avatar className="h-8 w-8">
						{metadata.author_avatar_url && (
							<AvatarImage src={metadata.author_avatar_url} alt={metadata.author_name || "User"} />
						)}
						<AvatarFallback className="text-[10px] bg-primary/10 text-primary">
							{getInitials(metadata.author_name, metadata.author_email)}
						</AvatarFallback>
					</Avatar>
				);
			}
			return (
				<Avatar className="h-8 w-8">
					<AvatarFallback className="text-[10px] bg-primary/10 text-primary">
						{getInitials(null, null)}
					</AvatarFallback>
				</Avatar>
			);
		}

		if (item.type === "page_limit_exceeded") {
			return (
				<div className="h-8 w-8 flex items-center justify-center rounded-full bg-amber-500/10">
					<AlertTriangle className="h-4 w-4 text-amber-500" />
				</div>
			);
		}

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
		if (activeTab === "comments") {
			return {
				title: t("no_comments") || "No comments",
				hint: t("no_comments_hint") || "You'll see mentions and replies here",
			};
		}
		return {
			title: t("no_status_updates") || "No status updates",
			hint: t("no_status_updates_hint") || "Document and connector updates will appear here",
		};
	};

	if (!mounted) return null;

	const isLoading = isSearchMode ? isSearchLoading : activeSource.loading;

	return (
		<>
			<div className="shrink-0 p-4 pb-2 space-y-3">
				<div className="flex items-center justify-between">
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
						<h2 className="text-lg font-semibold">{t("inbox") || "Inbox"}</h2>
					</div>
					<div className="flex items-center gap-1">
						{isMobile ? (
							<>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7 rounded-full"
									onClick={() => setFilterDrawerOpen(true)}
								>
									<ListFilter className="h-4 w-4 text-muted-foreground" />
									<span className="sr-only">{t("filter") || "Filter"}</span>
								</Button>
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
													{activeTab === "status" && (
														<button
															type="button"
															onClick={() => {
																setActiveFilter("errors");
																setFilterDrawerOpen(false);
															}}
															className={cn(
																"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
																activeFilter === "errors"
																	? "bg-primary/10 text-primary"
																	: "hover:bg-muted"
															)}
														>
															<span className="flex items-center gap-2">
																<AlertCircle className="h-4 w-4" />
																<span>{t("errors_only") || "Errors only"}</span>
															</span>
															{activeFilter === "errors" && <Check className="h-4 w-4" />}
														</button>
													)}
												</div>
											</div>
											{activeTab === "status" && statusSourceOptions.length > 0 && (
												<div className="space-y-2">
													<p className="text-xs text-muted-foreground/80 font-medium px-1">
														{t("sources") || "Sources"}
													</p>
													<div className="space-y-1">
														<button
															type="button"
															onClick={() => {
																setSelectedSource(null);
																setFilterDrawerOpen(false);
															}}
															className={cn(
																"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
																selectedSource === null
																	? "bg-primary/10 text-primary"
																	: "hover:bg-muted"
															)}
														>
															<span className="flex items-center gap-2">
																<LayoutGrid className="h-4 w-4" />
																<span>{t("all_sources") || "All sources"}</span>
															</span>
															{selectedSource === null && <Check className="h-4 w-4" />}
														</button>
														{statusSourceOptions.map((source) => (
															<button
																key={source.key}
																type="button"
																onClick={() => {
																	setSelectedSource(source.key);
																	setFilterDrawerOpen(false);
																}}
																className={cn(
																	"flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
																	selectedSource === source.key
																		? "bg-primary/10 text-primary"
																		: "hover:bg-muted"
																)}
															>
																<span className="flex items-center gap-2">
																	{getConnectorIcon(source.type, "h-4 w-4")}
																	<span>{source.displayName}</span>
																</span>
																{selectedSource === source.key && <Check className="h-4 w-4" />}
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
							<DropdownMenu
								open={openDropdown === "filter"}
								onOpenChange={(isOpen) => setOpenDropdown(isOpen ? "filter" : null)}
							>
								<Tooltip>
									<TooltipTrigger asChild>
										<DropdownMenuTrigger asChild>
											<Button variant="ghost" size="icon" className="h-7 w-7 rounded-full">
												<ListFilter className="h-4 w-4 text-muted-foreground" />
												<span className="sr-only">{t("filter") || "Filter"}</span>
											</Button>
										</DropdownMenuTrigger>
									</TooltipTrigger>
									<TooltipContent className="z-80">{t("filter") || "Filter"}</TooltipContent>
								</Tooltip>
								<DropdownMenuContent
									align="end"
									className={cn(
										"z-80 select-none max-h-[60vh] overflow-hidden flex flex-col",
										activeTab === "status" ? "w-52" : "w-44"
									)}
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
									{activeTab === "status" && (
										<DropdownMenuItem
											onClick={() => setActiveFilter("errors")}
											className="flex items-center justify-between"
										>
											<span className="flex items-center gap-2">
												<AlertCircle className="h-4 w-4" />
												<span>{t("errors_only") || "Errors only"}</span>
											</span>
											{activeFilter === "errors" && <Check className="h-4 w-4" />}
										</DropdownMenuItem>
									)}
									{activeTab === "status" && statusSourceOptions.length > 0 && (
										<>
											<DropdownMenuLabel className="text-xs text-muted-foreground/80 font-normal mt-2">
												{t("sources") || "Sources"}
											</DropdownMenuLabel>
											<div
												className="relative max-h-[30vh] overflow-y-auto overflow-x-hidden -mb-1"
												onScroll={handleConnectorScroll}
												style={{
													maskImage: `linear-gradient(to bottom, ${connectorScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${connectorScrollPos === "bottom" ? "black" : "transparent"})`,
													WebkitMaskImage: `linear-gradient(to bottom, ${connectorScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${connectorScrollPos === "bottom" ? "black" : "transparent"})`,
												}}
											>
												<DropdownMenuItem
													onClick={() => setSelectedSource(null)}
													className="flex items-center justify-between"
												>
													<span className="flex items-center gap-2">
														<LayoutGrid className="h-4 w-4" />
														<span>{t("all_sources") || "All sources"}</span>
													</span>
													{selectedSource === null && <Check className="h-4 w-4" />}
												</DropdownMenuItem>
												{statusSourceOptions.map((source) => (
													<DropdownMenuItem
														key={source.key}
														onClick={() => setSelectedSource(source.key)}
														className="flex items-center justify-between"
													>
														<span className="flex items-center gap-2">
															{getConnectorIcon(source.type, "h-4 w-4")}
															<span>{source.displayName}</span>
														</span>
														{selectedSource === source.key && <Check className="h-4 w-4" />}
													</DropdownMenuItem>
												))}
											</div>
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
									className="h-7 w-7 rounded-full"
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
				onValueChange={(value) => {
					const tab = value as InboxTab;
					setActiveTab(tab);
					if (tab !== "status" && activeFilter === "errors") {
						setActiveFilter("all");
					}
				}}
				className="shrink-0 mx-4 mt-2"
			>
				<TabsList stretch showBottomBorder size="sm">
					<TabsTrigger value="comments">
						<span className="inline-flex items-center gap-1.5">
							<MessageSquare className="h-4 w-4" />
							<span>{t("comments") || "Comments"}</span>
							<span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium">
								{formatInboxCount(comments.unreadCount)}
							</span>
						</span>
					</TabsTrigger>
					<TabsTrigger value="status">
						<span className="inline-flex items-center gap-1.5">
							<History className="h-4 w-4" />
							<span>{t("status") || "Status"}</span>
							<span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-primary/20 text-muted-foreground text-xs font-medium">
								{formatInboxCount(status.unreadCount)}
							</span>
						</span>
					</TabsTrigger>
				</TabsList>
			</Tabs>

			<div className="flex-1 overflow-y-auto overflow-x-hidden p-2">
				{isLoading ? (
					<div className="space-y-2">
						{activeTab === "comments"
							? [85, 60, 90, 70, 50, 75].map((titleWidth) => (
									<div
										key={`skeleton-comment-${titleWidth}`}
										className="flex items-center gap-3 rounded-lg px-3 py-3 h-[80px]"
									>
										<Skeleton className="h-8 w-8 rounded-full shrink-0" />
										<div className="flex-1 min-w-0 space-y-2">
											<Skeleton className="h-3 rounded" style={{ width: `${titleWidth}%` }} />
											<Skeleton className="h-2.5 w-[70%] rounded" />
										</div>
										<Skeleton className="h-3 w-6 shrink-0 rounded" />
									</div>
								))
							: [75, 90, 55, 80, 65, 85].map((titleWidth) => (
									<div
										key={`skeleton-status-${titleWidth}`}
										className="flex items-center gap-3 rounded-lg px-3 py-3 h-[80px]"
									>
										<Skeleton className="h-8 w-8 rounded-full shrink-0" />
										<div className="flex-1 min-w-0 space-y-2">
											<Skeleton className="h-3 rounded" style={{ width: `${titleWidth}%` }} />
											<Skeleton className="h-2.5 w-[60%] rounded" />
										</div>
										<div className="flex items-center gap-1.5 shrink-0">
											<Skeleton className="h-3 w-6 rounded" />
											<Skeleton className="h-2 w-2 rounded-full" />
										</div>
									</div>
								))}
					</div>
				) : filteredItems.length > 0 ? (
					<div className="space-y-2">
						{filteredItems.map((item, index) => {
							const isMarkingAsRead = markingAsReadId === item.id;
							const isPrefetchTrigger =
								!isSearchMode && activeSource.hasMore && index === filteredItems.length - 5;

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
									style={{ contentVisibility: "auto", containIntrinsicSize: "0 80px" }}
								>
									{activeTab === "status" ? (
										<Tooltip delayDuration={600}>
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
									) : (
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
									)}

									<div className="flex items-center justify-end gap-1.5 shrink-0 w-10">
										<span className="text-[10px] text-muted-foreground">
											{formatTime(item.created_at)}
										</span>
										{!item.read && <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />}
									</div>
								</div>
							);
						})}
						{!isSearchMode && filteredItems.length < 5 && activeSource.hasMore && (
							<div ref={prefetchTriggerRef} className="h-1" />
						)}
						{activeSource.loadingMore &&
							(activeTab === "comments"
								? [80, 60, 90].map((titleWidth) => (
										<div
											key={`loading-more-comment-${titleWidth}`}
											className="flex items-center gap-3 rounded-lg px-3 py-3 h-[80px]"
										>
											<Skeleton className="h-8 w-8 rounded-full shrink-0" />
											<div className="flex-1 min-w-0 space-y-2">
												<Skeleton className="h-3 rounded" style={{ width: `${titleWidth}%` }} />
												<Skeleton className="h-2.5 w-[70%] rounded" />
											</div>
											<Skeleton className="h-3 w-6 shrink-0 rounded" />
										</div>
									))
								: [70, 85, 55].map((titleWidth) => (
										<div
											key={`loading-more-status-${titleWidth}`}
											className="flex items-center gap-3 rounded-lg px-3 py-3 h-[80px]"
										>
											<Skeleton className="h-8 w-8 rounded-full shrink-0" />
											<div className="flex-1 min-w-0 space-y-2">
												<Skeleton className="h-3 rounded" style={{ width: `${titleWidth}%` }} />
												<Skeleton className="h-2.5 w-[60%] rounded" />
											</div>
											<div className="flex items-center gap-1.5 shrink-0">
												<Skeleton className="h-3 w-6 rounded" />
												<Skeleton className="h-2 w-2 rounded-full" />
											</div>
										</div>
									)))}
					</div>
				) : isSearchMode ? (
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
						{activeTab === "comments" ? (
							<MessageSquare className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
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
}

export function InboxSidebar({
	open,
	onOpenChange,
	comments,
	status,
	totalUnreadCount,
	onCloseMobileSidebar,
}: InboxSidebarProps) {
	const t = useTranslations("sidebar");

	return (
		<SidebarSlideOutPanel open={open} onOpenChange={onOpenChange} ariaLabel={t("inbox") || "Inbox"}>
			<InboxSidebarContent
				onOpenChange={onOpenChange}
				comments={comments}
				status={status}
				totalUnreadCount={totalUnreadCount}
				onCloseMobileSidebar={onCloseMobileSidebar}
			/>
		</SidebarSlideOutPanel>
	);
}
