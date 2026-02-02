"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { AlertTriangle, Inbox, LogOut, SquareLibrary, Trash2 } from "lucide-react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { currentThreadAtom, resetCurrentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { deleteSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { searchSpacesAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { isPageLimitExceededMetadata } from "@/contracts/types/inbox.types";
import { useInbox } from "@/hooks/use-inbox";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { deleteThread, fetchThreads, updateThread } from "@/lib/chat/thread-persistence";
import { cleanupElectric } from "@/lib/electric/client";
import { resetUser, trackLogout } from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import type { ChatItem, NavItem, SearchSpace } from "../types/layout.types";
import { CreateSearchSpaceDialog } from "../ui/dialogs";
import { LayoutShell } from "../ui/shell";
import { AllPrivateChatsSidebar } from "../ui/sidebar/AllPrivateChatsSidebar";
import { AllSharedChatsSidebar } from "../ui/sidebar/AllSharedChatsSidebar";

interface LayoutDataProviderProps {
	searchSpaceId: string;
	children: React.ReactNode;
	breadcrumb?: React.ReactNode;
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

export function LayoutDataProvider({
	searchSpaceId,
	children,
	breadcrumb,
}: LayoutDataProviderProps) {
	const t = useTranslations("dashboard");
	const tCommon = useTranslations("common");
	const tSidebar = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const pathname = usePathname();
	const queryClient = useQueryClient();
	const { theme, setTheme } = useTheme();

	// Atoms
	const { data: user } = useAtomValue(currentUserAtom);
	const { data: searchSpacesData, refetch: refetchSearchSpaces } = useAtomValue(searchSpacesAtom);
	const { mutateAsync: deleteSearchSpace } = useAtomValue(deleteSearchSpaceMutationAtom);
	const currentThreadState = useAtomValue(currentThreadAtom);
	const resetCurrentThread = useSetAtom(resetCurrentThreadAtom);

	// State for handling new chat navigation when router is out of sync
	const [pendingNewChat, setPendingNewChat] = useState(false);

	// Current IDs from URL, with fallback to atom for replaceState updates
	const currentChatId = params?.chat_id
		? Number(Array.isArray(params.chat_id) ? params.chat_id[0] : params.chat_id)
		: currentThreadState.id;

	// Fetch current search space (for caching purposes)
	useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: Number(searchSpaceId) }),
		enabled: !!searchSpaceId,
	});

	// Fetch threads (40 total to allow up to 20 per section - shared/private)
	const { data: threadsData } = useQuery({
		queryKey: ["threads", searchSpaceId, { limit: 40 }],
		queryFn: () => fetchThreads(Number(searchSpaceId), 40),
		enabled: !!searchSpaceId,
	});

	// Separate sidebar states for shared and private chats
	const [isAllSharedChatsSidebarOpen, setIsAllSharedChatsSidebarOpen] = useState(false);
	const [isAllPrivateChatsSidebarOpen, setIsAllPrivateChatsSidebarOpen] = useState(false);

	// Inbox sidebar state
	const [isInboxSidebarOpen, setIsInboxSidebarOpen] = useState(false);
	const [isInboxDocked, setIsInboxDocked] = useState(false);

	// Search space dialog state
	const [isCreateSearchSpaceDialogOpen, setIsCreateSearchSpaceDialogOpen] = useState(false);

	// Inbox hooks - separate data sources for mentions and status tabs
	// This ensures each tab has independent pagination and data loading
	const userId = user?.id ? String(user.id) : null;

	// Mentions: Only fetch "new_mention" type notifications
	const {
		inboxItems: mentionItems,
		unreadCount: mentionUnreadCount,
		loading: mentionLoading,
		loadingMore: mentionLoadingMore,
		hasMore: mentionHasMore,
		loadMore: mentionLoadMore,
		markAsRead: markMentionAsRead,
		markAllAsRead: markAllMentionsAsRead,
	} = useInbox(userId, Number(searchSpaceId) || null, "new_mention");

	// Status: Fetch all types (will be filtered client-side to status types)
	// We pass null to get all, then InboxSidebar filters to status types
	const {
		inboxItems: statusItems,
		unreadCount: statusUnreadCount,
		loading: statusLoading,
		loadingMore: statusLoadingMore,
		hasMore: statusHasMore,
		loadMore: statusLoadMore,
		markAsRead: markStatusAsRead,
		markAllAsRead: markAllStatusAsRead,
	} = useInbox(userId, Number(searchSpaceId) || null, null);

	// Combined unread count for nav badge (mentions take priority for visibility)
	const totalUnreadCount = mentionUnreadCount + statusUnreadCount;

	// Track seen notification IDs to detect new page_limit_exceeded notifications
	const seenPageLimitNotifications = useRef<Set<number>>(new Set());
	const isInitialLoad = useRef(true);

	// Effect to show toast for new page_limit_exceeded notifications
	useEffect(() => {
		if (statusLoading) return;

		// Get page_limit_exceeded notifications
		const pageLimitNotifications = statusItems.filter(
			(item) => item.type === "page_limit_exceeded"
		);

		// On initial load, just mark all as seen without showing toasts
		if (isInitialLoad.current) {
			for (const notification of pageLimitNotifications) {
				seenPageLimitNotifications.current.add(notification.id);
			}
			isInitialLoad.current = false;
			return;
		}

		// Find new notifications (not yet seen)
		const newNotifications = pageLimitNotifications.filter(
			(notification) => !seenPageLimitNotifications.current.has(notification.id)
		);

		// Show toast for each new page_limit_exceeded notification
		for (const notification of newNotifications) {
			seenPageLimitNotifications.current.add(notification.id);

			// Extract metadata for navigation
			const actionUrl = isPageLimitExceededMetadata(notification.metadata)
				? notification.metadata.action_url
				: `/dashboard/${searchSpaceId}/more-pages`;

			toast.error(notification.title, {
				description: notification.message,
				duration: 8000,
				icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
				action: {
					label: "View Plans",
					onClick: () => router.push(actionUrl),
				},
			});
		}
	}, [statusItems, statusLoading, searchSpaceId, router]);

	// Unified mark as read that delegates to the correct hook
	const markAsRead = useCallback(
		async (id: number) => {
			// Try both - one will succeed based on which list has the item
			const mentionResult = await markMentionAsRead(id);
			if (mentionResult) return true;
			return markStatusAsRead(id);
		},
		[markMentionAsRead, markStatusAsRead]
	);

	// Mark all as read for both types
	const markAllAsRead = useCallback(async () => {
		await Promise.all([markAllMentionsAsRead(), markAllStatusAsRead()]);
		return true;
	}, [markAllMentionsAsRead, markAllStatusAsRead]);

	// Delete dialogs state
	const [showDeleteChatDialog, setShowDeleteChatDialog] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; name: string } | null>(null);
	const [isDeletingChat, setIsDeletingChat] = useState(false);

	// Delete/Leave search space dialog state
	const [showDeleteSearchSpaceDialog, setShowDeleteSearchSpaceDialog] = useState(false);
	const [showLeaveSearchSpaceDialog, setShowLeaveSearchSpaceDialog] = useState(false);
	const [searchSpaceToDelete, setSearchSpaceToDelete] = useState<SearchSpace | null>(null);
	const [searchSpaceToLeave, setSearchSpaceToLeave] = useState<SearchSpace | null>(null);
	const [isDeletingSearchSpace, setIsDeletingSearchSpace] = useState(false);
	const [isLeavingSearchSpace, setIsLeavingSearchSpace] = useState(false);

	// Effect to complete new chat navigation after router syncs
	// This runs when handleNewChat detected an out-of-sync state and triggered a sync
	useEffect(() => {
		if (pendingNewChat && params?.chat_id) {
			// Router is now synced (chat_id is in params), complete navigation to new-chat
			resetCurrentThread();
			router.push(`/dashboard/${searchSpaceId}/new-chat`);
			setPendingNewChat(false);
		}
	}, [pendingNewChat, params?.chat_id, router, searchSpaceId, resetCurrentThread]);

	const searchSpaces: SearchSpace[] = useMemo(() => {
		if (!searchSpacesData || !Array.isArray(searchSpacesData)) return [];
		return searchSpacesData.map((space) => ({
			id: space.id,
			name: space.name,
			description: space.description,
			isOwner: space.is_owner,
			memberCount: space.member_count || 0,
			createdAt: space.created_at,
		}));
	}, [searchSpacesData]);

	// Find active search space from list (has is_owner and member_count)
	const activeSearchSpace: SearchSpace | null = useMemo(() => {
		if (!searchSpaceId || !searchSpaces.length) return null;
		return searchSpaces.find((s) => s.id === Number(searchSpaceId)) ?? null;
	}, [searchSpaceId, searchSpaces]);

	// Transform and split chats into private and shared based on visibility
	const { myChats, sharedChats } = useMemo(() => {
		if (!threadsData?.threads) return { myChats: [], sharedChats: [] };

		const privateChats: ChatItem[] = [];
		const sharedChatsList: ChatItem[] = [];

		for (const thread of threadsData.threads) {
			const chatItem: ChatItem = {
				id: thread.id,
				name: thread.title || `Chat ${thread.id}`,
				url: `/dashboard/${searchSpaceId}/new-chat/${thread.id}`,
				visibility: thread.visibility,
				isOwnThread: thread.is_own_thread,
				archived: thread.archived,
			};

			// Split based on visibility, not ownership:
			// - PRIVATE chats go to "Private Chats" section
			// - SEARCH_SPACE chats go to "Shared Chats" section
			if (thread.visibility === "SEARCH_SPACE") {
				sharedChatsList.push(chatItem);
			} else {
				privateChats.push(chatItem);
			}
		}

		return { myChats: privateChats, sharedChats: sharedChatsList };
	}, [threadsData, searchSpaceId]);

	// Navigation items
	const navItems: NavItem[] = useMemo(
		() => [
			{
				title: "Inbox",
				url: "#inbox", // Special URL to indicate this is handled differently
				icon: Inbox,
				isActive: isInboxSidebarOpen,
				badge: totalUnreadCount > 0 ? formatInboxCount(totalUnreadCount) : undefined,
			},
			{
				title: "Documents",
				url: `/dashboard/${searchSpaceId}/documents`,
				icon: SquareLibrary,
				isActive: pathname?.includes("/documents"),
			},
		],
		[searchSpaceId, pathname, isInboxSidebarOpen, totalUnreadCount]
	);

	// Handlers
	const handleSearchSpaceSelect = useCallback(
		(id: number) => {
			router.push(`/dashboard/${id}/new-chat`);
		},
		[router]
	);

	const handleAddSearchSpace = useCallback(() => {
		setIsCreateSearchSpaceDialogOpen(true);
	}, []);

	const handleUserSettings = useCallback(() => {
		router.push("/dashboard/user/settings");
	}, [router]);

	const handleSearchSpaceSettings = useCallback(
		(space: SearchSpace) => {
			router.push(`/dashboard/${space.id}/settings`);
		},
		[router]
	);

	const handleSearchSpaceDeleteClick = useCallback((space: SearchSpace) => {
		// If user is owner, show delete dialog; otherwise show leave dialog
		if (space.isOwner) {
			setSearchSpaceToDelete(space);
			setShowDeleteSearchSpaceDialog(true);
		} else {
			setSearchSpaceToLeave(space);
			setShowLeaveSearchSpaceDialog(true);
		}
	}, []);

	const confirmDeleteSearchSpace = useCallback(async () => {
		if (!searchSpaceToDelete) return;
		setIsDeletingSearchSpace(true);
		try {
			await deleteSearchSpace({ id: searchSpaceToDelete.id });
			refetchSearchSpaces();
			if (Number(searchSpaceId) === searchSpaceToDelete.id && searchSpaces.length > 1) {
				const remaining = searchSpaces.filter((s) => s.id !== searchSpaceToDelete.id);
				if (remaining.length > 0) {
					router.push(`/dashboard/${remaining[0].id}/new-chat`);
				}
			} else if (searchSpaces.length === 1) {
				router.push("/dashboard");
			}
		} catch (error) {
			console.error("Error deleting search space:", error);
		} finally {
			setIsDeletingSearchSpace(false);
			setShowDeleteSearchSpaceDialog(false);
			setSearchSpaceToDelete(null);
		}
	}, [
		searchSpaceToDelete,
		deleteSearchSpace,
		refetchSearchSpaces,
		searchSpaceId,
		searchSpaces,
		router,
	]);

	const confirmLeaveSearchSpace = useCallback(async () => {
		if (!searchSpaceToLeave) return;
		setIsLeavingSearchSpace(true);
		try {
			await searchSpacesApiService.leaveSearchSpace(searchSpaceToLeave.id);
			refetchSearchSpaces();
			if (Number(searchSpaceId) === searchSpaceToLeave.id && searchSpaces.length > 1) {
				const remaining = searchSpaces.filter((s) => s.id !== searchSpaceToLeave.id);
				if (remaining.length > 0) {
					router.push(`/dashboard/${remaining[0].id}/new-chat`);
				}
			} else if (searchSpaces.length === 1) {
				router.push("/dashboard");
			}
		} catch (error) {
			console.error("Error leaving search space:", error);
		} finally {
			setIsLeavingSearchSpace(false);
			setShowLeaveSearchSpaceDialog(false);
			setSearchSpaceToLeave(null);
		}
	}, [searchSpaceToLeave, refetchSearchSpaces, searchSpaceId, searchSpaces, router]);

	const handleNavItemClick = useCallback(
		(item: NavItem) => {
			// Handle inbox specially - toggle sidebar instead of navigating
			if (item.url === "#inbox") {
				setIsInboxSidebarOpen((prev) => !prev);
				return;
			}
			router.push(item.url);
		},
		[router]
	);

	const handleNewChat = useCallback(() => {
		// Check if router is out of sync (thread created via replaceState but params don't have chat_id)
		const isOutOfSync = currentThreadState.id !== null && !params?.chat_id;

		if (isOutOfSync) {
			// First sync Next.js router by navigating to the current chat's actual URL
			// This updates the router's internal state to match the browser URL
			router.replace(`/dashboard/${searchSpaceId}/new-chat/${currentThreadState.id}`);
			// Set flag to trigger navigation to new-chat after params update
			setPendingNewChat(true);
		} else {
			// Normal navigation - router is in sync
			router.push(`/dashboard/${searchSpaceId}/new-chat`);
		}
	}, [router, searchSpaceId, currentThreadState.id, params?.chat_id]);

	const handleChatSelect = useCallback(
		(chat: ChatItem) => {
			router.push(chat.url);
		},
		[router]
	);

	const handleChatDelete = useCallback((chat: ChatItem) => {
		setChatToDelete({ id: chat.id, name: chat.name });
		setShowDeleteChatDialog(true);
	}, []);

	const handleChatArchive = useCallback(
		async (chat: ChatItem) => {
			const newArchivedState = !chat.archived;
			const successMessage = newArchivedState
				? tSidebar("chat_archived") || "Chat archived"
				: tSidebar("chat_unarchived") || "Chat restored";

			try {
				await updateThread(chat.id, { archived: newArchivedState });
				toast.success(successMessage);
				// Invalidate queries to refresh UI (React Query will only refetch active queries)
				queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["all-threads", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["search-threads", searchSpaceId] });
			} catch (error) {
				console.error("Error archiving thread:", error);
				toast.error(tSidebar("error_archiving_chat") || "Failed to archive chat");
			}
		},
		[queryClient, searchSpaceId, tSidebar]
	);

	const handleSettings = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/settings`);
	}, [router, searchSpaceId]);

	const handleManageMembers = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/team`);
	}, [router, searchSpaceId]);

	const handleLogout = useCallback(async () => {
		try {
			trackLogout();
			resetUser();

			// Best-effort cleanup of Electric SQL / PGlite
			// Even if this fails, login-time cleanup will handle it
			try {
				await cleanupElectric();
			} catch (err) {
				console.warn("[Logout] Electric cleanup failed (will be handled on next login):", err);
			}

			if (typeof window !== "undefined") {
				localStorage.removeItem("surfsense_bearer_token");
				router.push("/");
			}
		} catch (error) {
			console.error("Error during logout:", error);
			router.push("/");
		}
	}, [router]);

	const handleViewAllSharedChats = useCallback(() => {
		setIsAllSharedChatsSidebarOpen(true);
	}, []);

	const handleViewAllPrivateChats = useCallback(() => {
		setIsAllPrivateChatsSidebarOpen(true);
	}, []);

	// Delete handlers
	const confirmDeleteChat = useCallback(async () => {
		if (!chatToDelete) return;
		setIsDeletingChat(true);
		try {
			await deleteThread(chatToDelete.id);
			queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
			if (currentChatId === chatToDelete.id) {
				router.push(`/dashboard/${searchSpaceId}/new-chat`);
			}
		} catch (error) {
			console.error("Error deleting thread:", error);
		} finally {
			setIsDeletingChat(false);
			setShowDeleteChatDialog(false);
			setChatToDelete(null);
		}
	}, [chatToDelete, queryClient, searchSpaceId, router, currentChatId]);

	// Page usage
	const pageUsage = user
		? {
				pagesUsed: user.pages_used,
				pagesLimit: user.pages_limit,
			}
		: undefined;

	// Detect if we're on the chat page (needs overflow-hidden for chat's own scroll)
	const isChatPage = pathname?.includes("/new-chat") ?? false;

	return (
		<>
			<LayoutShell
				searchSpaces={searchSpaces}
				activeSearchSpaceId={Number(searchSpaceId)}
				onSearchSpaceSelect={handleSearchSpaceSelect}
				onSearchSpaceDelete={handleSearchSpaceDeleteClick}
				onSearchSpaceSettings={handleSearchSpaceSettings}
				onAddSearchSpace={handleAddSearchSpace}
				searchSpace={activeSearchSpace}
				navItems={navItems}
				onNavItemClick={handleNavItemClick}
				chats={myChats}
				sharedChats={sharedChats}
				activeChatId={currentChatId}
				onNewChat={handleNewChat}
				onChatSelect={handleChatSelect}
				onChatDelete={handleChatDelete}
				onChatArchive={handleChatArchive}
				onViewAllSharedChats={handleViewAllSharedChats}
				onViewAllPrivateChats={handleViewAllPrivateChats}
				user={{
					email: user?.email || "",
					name: user?.display_name || user?.email?.split("@")[0],
					avatarUrl: user?.avatar_url || undefined,
				}}
				onSettings={handleSettings}
				onManageMembers={handleManageMembers}
				onUserSettings={handleUserSettings}
				onLogout={handleLogout}
				pageUsage={pageUsage}
				breadcrumb={breadcrumb}
				theme={theme}
				setTheme={setTheme}
				isChatPage={isChatPage}
				inbox={{
					isOpen: isInboxSidebarOpen,
					onOpenChange: setIsInboxSidebarOpen,
					// Separate data sources for each tab
					mentions: {
						items: mentionItems,
						unreadCount: mentionUnreadCount,
						loading: mentionLoading,
						loadingMore: mentionLoadingMore,
						hasMore: mentionHasMore,
						loadMore: mentionLoadMore,
					},
					status: {
						items: statusItems,
						unreadCount: statusUnreadCount,
						loading: statusLoading,
						loadingMore: statusLoadingMore,
						hasMore: statusHasMore,
						loadMore: statusLoadMore,
					},
					totalUnreadCount,
					markAsRead,
					markAllAsRead,
					isDocked: isInboxDocked,
					onDockedChange: setIsInboxDocked,
				}}
			>
				{children}
			</LayoutShell>

			{/* Delete Chat Dialog */}
			<Dialog open={showDeleteChatDialog} onOpenChange={setShowDeleteChatDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>{t("delete_chat")}</span>
						</DialogTitle>
						<DialogDescription>
							{t("delete_chat_confirm")} <span className="font-medium">{chatToDelete?.name}</span>?{" "}
							{t("action_cannot_undone")}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowDeleteChatDialog(false)}
							disabled={isDeletingChat}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							onClick={confirmDeleteChat}
							disabled={isDeletingChat}
							className="gap-2"
						>
							{isDeletingChat ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									{t("deleting")}
								</>
							) : (
								<>
									<Trash2 className="h-4 w-4" />
									{tCommon("delete")}
								</>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete Search Space Dialog */}
			<Dialog open={showDeleteSearchSpaceDialog} onOpenChange={setShowDeleteSearchSpaceDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>{t("delete_search_space")}</span>
						</DialogTitle>
						<DialogDescription>
							{t("delete_space_confirm", { name: searchSpaceToDelete?.name || "" })}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowDeleteSearchSpaceDialog(false)}
							disabled={isDeletingSearchSpace}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							onClick={confirmDeleteSearchSpace}
							disabled={isDeletingSearchSpace}
							className="gap-2"
						>
							{isDeletingSearchSpace ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									{t("deleting")}
								</>
							) : (
								<>
									<Trash2 className="h-4 w-4" />
									{tCommon("delete")}
								</>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Leave Search Space Dialog */}
			<Dialog open={showLeaveSearchSpaceDialog} onOpenChange={setShowLeaveSearchSpaceDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<LogOut className="h-5 w-5 text-destructive" />
							<span>{t("leave_title")}</span>
						</DialogTitle>
						<DialogDescription>
							{t("leave_confirm", { name: searchSpaceToLeave?.name || "" })}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowLeaveSearchSpaceDialog(false)}
							disabled={isLeavingSearchSpace}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							onClick={confirmLeaveSearchSpace}
							disabled={isLeavingSearchSpace}
							className="gap-2"
						>
							{isLeavingSearchSpace ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									{t("leaving")}
								</>
							) : (
								<>
									<LogOut className="h-4 w-4" />
									{t("leave")}
								</>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* All Shared Chats Sidebar */}
			<AllSharedChatsSidebar
				open={isAllSharedChatsSidebarOpen}
				onOpenChange={setIsAllSharedChatsSidebarOpen}
				searchSpaceId={searchSpaceId}
			/>

			{/* All Private Chats Sidebar */}
			<AllPrivateChatsSidebar
				open={isAllPrivateChatsSidebarOpen}
				onOpenChange={setIsAllPrivateChatsSidebarOpen}
				searchSpaceId={searchSpaceId}
			/>

			{/* Create Search Space Dialog */}
			<CreateSearchSpaceDialog
				open={isCreateSearchSpaceDialogOpen}
				onOpenChange={setIsCreateSearchSpaceDialogOpen}
			/>
		</>
	);
}
