"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { AlertTriangle, Inbox, Megaphone, SquareLibrary } from "lucide-react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { currentThreadAtom, resetCurrentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import { rightPanelCollapsedAtom } from "@/atoms/layout/right-panel.atom";
import { deleteSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { searchSpacesAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import {
	morePagesDialogAtom,
	searchSpaceSettingsDialogAtom,
	teamDialogAtom,
	userSettingsDialogAtom,
} from "@/atoms/settings/settings-dialog.atoms";
import { resetTabsAtom, syncChatTabAtom, type Tab } from "@/atoms/tabs/tabs.atom";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { MorePagesDialog } from "@/components/settings/more-pages-dialog";
import { SearchSpaceSettingsDialog } from "@/components/settings/search-space-settings-dialog";
import { TeamDialog } from "@/components/settings/team-dialog";
import { UserSettingsDialog } from "@/components/settings/user-settings-dialog";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useAnnouncements } from "@/hooks/use-announcements";
import { useDocumentsProcessing } from "@/hooks/use-documents-processing";
import { useInbox } from "@/hooks/use-inbox";
import { useIsMobile } from "@/hooks/use-mobile";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { logout } from "@/lib/auth-utils";
import { deleteThread, fetchThreads, updateThread } from "@/lib/chat/thread-persistence";
import { resetUser, trackLogout } from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import type { ChatItem, NavItem, SearchSpace } from "../types/layout.types";
import { CreateSearchSpaceDialog } from "../ui/dialogs";
import { LayoutShell } from "../ui/shell";

interface LayoutDataProviderProps {
	searchSpaceId: string;
	children: React.ReactNode;
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

export function LayoutDataProvider({ searchSpaceId, children }: LayoutDataProviderProps) {
	const t = useTranslations("dashboard");
	const tCommon = useTranslations("common");
	const tSidebar = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const pathname = usePathname();
	const queryClient = useQueryClient();
	const { theme, setTheme } = useTheme();
	const isMobile = useIsMobile();

	// Announcements
	const { unreadCount: announcementUnreadCount } = useAnnouncements();

	// Atoms
	const { data: user } = useAtomValue(currentUserAtom);
	const {
		data: searchSpacesData,
		refetch: refetchSearchSpaces,
		isSuccess: searchSpacesLoaded,
	} = useAtomValue(searchSpacesAtom);
	const { mutateAsync: deleteSearchSpace } = useAtomValue(deleteSearchSpaceMutationAtom);
	const currentThreadState = useAtomValue(currentThreadAtom);
	const resetCurrentThread = useSetAtom(resetCurrentThreadAtom);
	const syncChatTab = useSetAtom(syncChatTabAtom);
	const resetTabs = useSetAtom(resetTabsAtom);

	// State for handling new chat navigation when router is out of sync
	const [pendingNewChat, setPendingNewChat] = useState(false);

	// Key used to force-remount the page component (e.g. after deleting the active chat
	// when the router is out of sync due to replaceState)
	const [chatResetKey, setChatResetKey] = useState(0);

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
	const { data: threadsData, isPending: isLoadingThreads } = useQuery({
		queryKey: ["threads", searchSpaceId, { limit: 40 }],
		queryFn: () => fetchThreads(Number(searchSpaceId), 40),
		enabled: !!searchSpaceId,
	});

	// Unified slide-out panel state (only one can be open at a time)
	type SlideoutPanel = "inbox" | "shared" | "private" | "announcements" | null;
	const [activeSlideoutPanel, setActiveSlideoutPanel] = useState<SlideoutPanel>(null);

	const isInboxSidebarOpen = activeSlideoutPanel === "inbox";
	const isAnnouncementsSidebarOpen = activeSlideoutPanel === "announcements";

	// Documents sidebar state (shared atom so Composer can toggle it)
	const [isDocumentsSidebarOpen, setIsDocumentsSidebarOpen] = useAtom(documentsSidebarOpenAtom);
	const [isDocumentsDocked, setIsDocumentsDocked] = useState(true);
	const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useAtom(rightPanelCollapsedAtom);

	// Open documents sidebar by default on desktop (docked mode)
	const documentsInitialized = useRef(false);
	useEffect(() => {
		if (!documentsInitialized.current) {
			documentsInitialized.current = true;
			const isDesktop = typeof window !== "undefined" && window.innerWidth >= 768;
			if (isDesktop) {
				setIsDocumentsSidebarOpen(true);
			}
		}
	}, [setIsDocumentsSidebarOpen]);

	// Search space dialog state
	const [isCreateSearchSpaceDialogOpen, setIsCreateSearchSpaceDialogOpen] = useState(false);

	const userId = user?.id ? String(user.id) : null;
	const numericSpaceId = Number(searchSpaceId) || null;

	// Batch-fetch unread counts for all categories in a single request
	// instead of 2 separate /unread-count calls.
	const { data: batchUnread, isLoading: isBatchUnreadLoading } = useQuery({
		queryKey: cacheKeys.notifications.batchUnreadCounts(numericSpaceId),
		queryFn: () => notificationsApiService.getBatchUnreadCounts(numericSpaceId ?? undefined),
		enabled: !!userId && !!numericSpaceId,
		staleTime: 30_000,
	});

	const commentsInbox = useInbox(
		userId,
		numericSpaceId,
		"comments",
		batchUnread?.comments,
		!isBatchUnreadLoading
	);
	const statusInbox = useInbox(
		userId,
		numericSpaceId,
		"status",
		batchUnread?.status,
		!isBatchUnreadLoading
	);

	const totalUnreadCount = commentsInbox.unreadCount + statusInbox.unreadCount;

	// Sync status inbox items to a shared atom so child components
	// (e.g. ConnectorPopup) can read them without creating duplicate useInbox hooks.
	const setStatusInboxItems = useSetAtom(statusInboxItemsAtom);
	useEffect(() => {
		setStatusInboxItems(statusInbox.inboxItems);
	}, [statusInbox.inboxItems, setStatusInboxItems]);

	// Document processing status — drives sidebar status indicator (spinner / check / error)
	const documentsProcessingStatus = useDocumentsProcessing(numericSpaceId);

	// Track seen notification IDs to detect new page_limit_exceeded notifications
	const seenPageLimitNotifications = useRef<Set<number>>(new Set());
	const isInitialLoad = useRef(true);

	const setMorePagesOpen = useSetAtom(morePagesDialogAtom);

	// Effect to show toast for new page_limit_exceeded notifications
	useEffect(() => {
		if (statusInbox.loading) return;

		const pageLimitNotifications = statusInbox.inboxItems.filter(
			(item) => item.type === "page_limit_exceeded"
		);

		if (isInitialLoad.current) {
			for (const notification of pageLimitNotifications) {
				seenPageLimitNotifications.current.add(notification.id);
			}
			isInitialLoad.current = false;
			return;
		}

		const newNotifications = pageLimitNotifications.filter(
			(notification) => !seenPageLimitNotifications.current.has(notification.id)
		);

		for (const notification of newNotifications) {
			seenPageLimitNotifications.current.add(notification.id);

			toast.error(notification.title, {
				description: notification.message,
				duration: 8000,
				icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
				action: {
					label: "View Plans",
					onClick: () => setMorePagesOpen(true),
				},
			});
		}
	}, [statusInbox.inboxItems, statusInbox.loading, searchSpaceId, setMorePagesOpen]);

	// Delete dialogs state
	const [showDeleteChatDialog, setShowDeleteChatDialog] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; name: string } | null>(null);
	const [isDeletingChat, setIsDeletingChat] = useState(false);

	// Rename dialog state
	const [showRenameChatDialog, setShowRenameChatDialog] = useState(false);
	const [chatToRename, setChatToRename] = useState<{ id: number; name: string } | null>(null);
	const [newChatTitle, setNewChatTitle] = useState("");
	const [isRenamingChat, setIsRenamingChat] = useState(false);

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

	// Reset transient slide-out panels and tabs when switching search spaces.
	// Use a ref to skip the initial mount — only reset when the space actually changes.
	const prevSearchSpaceIdRef = useRef(searchSpaceId);
	useEffect(() => {
		if (prevSearchSpaceIdRef.current !== searchSpaceId) {
			prevSearchSpaceIdRef.current = searchSpaceId;
			setActiveSlideoutPanel(null);
			resetTabs();
		}
	}, [searchSpaceId, resetTabs]);

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

	// Safety redirect: if the current search space is no longer in the user's list
	// (e.g. deleted by background task, membership revoked), redirect to a valid space.
	useEffect(() => {
		if (!searchSpacesLoaded || !searchSpaceId || isDeletingSearchSpace || isLeavingSearchSpace)
			return;
		if (searchSpaces.length > 0 && !activeSearchSpace) {
			router.replace(`/dashboard/${searchSpaces[0].id}/new-chat`);
		} else if (searchSpaces.length === 0 && searchSpacesLoaded) {
			router.replace("/dashboard");
		}
	}, [
		searchSpacesLoaded,
		searchSpaceId,
		searchSpaces,
		activeSearchSpace,
		isDeletingSearchSpace,
		isLeavingSearchSpace,
		router,
	]);

	// Sync current chat route with tab state
	useEffect(() => {
		const chatId = currentChatId ?? null;
		const chatUrl = chatId
			? `/dashboard/${searchSpaceId}/new-chat/${chatId}`
			: `/dashboard/${searchSpaceId}/new-chat`;
		const thread = threadsData?.threads?.find((t) => t.id === chatId);
		syncChatTab({
			chatId,
			title: thread?.title || (chatId ? `Chat ${chatId}` : "New Chat"),
			chatUrl,
		});
	}, [currentChatId, searchSpaceId, threadsData?.threads, syncChatTab]);

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
				url: "#inbox",
				icon: Inbox,
				isActive: isInboxSidebarOpen,
				badge: totalUnreadCount > 0 ? formatInboxCount(totalUnreadCount) : undefined,
			},
			{
				title: "Documents",
				url: "#documents",
				icon: SquareLibrary,
				isActive: isMobile
					? isDocumentsSidebarOpen
					: isDocumentsSidebarOpen && !isRightPanelCollapsed,
				statusIndicator: documentsProcessingStatus,
			},
			{
				title: "Announcements",
				url: "#announcements",
				icon: Megaphone,
				isActive: isAnnouncementsSidebarOpen,
				badge: announcementUnreadCount > 0 ? formatInboxCount(announcementUnreadCount) : undefined,
			},
		],
		[
			isMobile,
			isInboxSidebarOpen,
			isDocumentsSidebarOpen,
			isRightPanelCollapsed,
			totalUnreadCount,
			isAnnouncementsSidebarOpen,
			announcementUnreadCount,
			documentsProcessingStatus,
		]
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

	const setUserSettingsDialog = useSetAtom(userSettingsDialogAtom);
	const setSearchSpaceSettingsDialog = useSetAtom(searchSpaceSettingsDialogAtom);
	const setTeamDialogOpen = useSetAtom(teamDialogAtom);

	const handleUserSettings = useCallback(() => {
		setUserSettingsDialog({ open: true, initialTab: "profile" });
	}, [setUserSettingsDialog]);

	const handleSearchSpaceSettings = useCallback(
		(_space: SearchSpace) => {
			setSearchSpaceSettingsDialog({ open: true, initialTab: "general" });
		},
		[setSearchSpaceSettingsDialog]
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

			const isCurrentSpace = Number(searchSpaceId) === searchSpaceToDelete.id;

			// Await refetch so we have the freshest list (backend now hides [DELETING] spaces)
			const result = await refetchSearchSpaces();
			const updatedSpaces = (result.data ?? []).filter((s) => s.id !== searchSpaceToDelete.id);

			if (isCurrentSpace) {
				if (updatedSpaces.length > 0) {
					router.push(`/dashboard/${updatedSpaces[0].id}/new-chat`);
				} else {
					router.push("/dashboard");
				}
			}
		} catch (error) {
			console.error("Error deleting search space:", error);
			toast.error(
				t.has("delete_space_error") ? t("delete_space_error") : "Failed to delete search space"
			);
		} finally {
			setIsDeletingSearchSpace(false);
			setShowDeleteSearchSpaceDialog(false);
			setSearchSpaceToDelete(null);
		}
	}, [searchSpaceToDelete, deleteSearchSpace, refetchSearchSpaces, searchSpaceId, router, t]);

	const confirmLeaveSearchSpace = useCallback(async () => {
		if (!searchSpaceToLeave) return;
		setIsLeavingSearchSpace(true);
		try {
			await searchSpacesApiService.leaveSearchSpace(searchSpaceToLeave.id);

			const isCurrentSpace = Number(searchSpaceId) === searchSpaceToLeave.id;

			const result = await refetchSearchSpaces();
			const updatedSpaces = (result.data ?? []).filter((s) => s.id !== searchSpaceToLeave.id);

			if (isCurrentSpace) {
				if (updatedSpaces.length > 0) {
					router.push(`/dashboard/${updatedSpaces[0].id}/new-chat`);
				} else {
					router.push("/dashboard");
				}
			}
		} catch (error) {
			console.error("Error leaving search space:", error);
			toast.error(t.has("leave_error") ? t("leave_error") : "Failed to leave search space");
		} finally {
			setIsLeavingSearchSpace(false);
			setShowLeaveSearchSpaceDialog(false);
			setSearchSpaceToLeave(null);
		}
	}, [searchSpaceToLeave, refetchSearchSpaces, searchSpaceId, router, t]);

	const handleTabSwitch = useCallback(
		(tab: Tab) => {
			if (tab.type === "chat") {
				const url = tab.chatUrl || `/dashboard/${searchSpaceId}/new-chat`;
				router.push(url);
			}
			// Document tabs are handled in-place by LayoutShell — no navigation needed
		},
		[router, searchSpaceId]
	);

	const handleNavItemClick = useCallback(
		(item: NavItem) => {
			if (item.url === "#inbox") {
				setActiveSlideoutPanel((prev) => (prev === "inbox" ? null : "inbox"));
				return;
			}
			if (item.url === "#documents") {
				if (!isMobile) {
					if (!isDocumentsSidebarOpen) {
						setIsDocumentsSidebarOpen(true);
						setIsRightPanelCollapsed(false);
						setActiveSlideoutPanel(null);
					} else {
						setIsRightPanelCollapsed((prev) => !prev);
					}
				} else {
					setIsDocumentsSidebarOpen((prev) => {
						if (!prev) {
							setActiveSlideoutPanel(null);
						}
						return !prev;
					});
				}
				return;
			}
			if (item.url === "#announcements") {
				setActiveSlideoutPanel((prev) => (prev === "announcements" ? null : "announcements"));
				return;
			}
			router.push(item.url);
		},
		[router, isMobile, isDocumentsSidebarOpen, setIsDocumentsSidebarOpen, setIsRightPanelCollapsed]
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

	const handleChatRename = useCallback((chat: ChatItem) => {
		setChatToRename({ id: chat.id, name: chat.name });
		setNewChatTitle(chat.name);
		setShowRenameChatDialog(true);
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
		setSearchSpaceSettingsDialog({ open: true, initialTab: "general" });
	}, [setSearchSpaceSettingsDialog]);

	const handleManageMembers = useCallback(() => {
		setTeamDialogOpen(true);
	}, [setTeamDialogOpen]);

	const handleLogout = useCallback(async () => {
		try {
			trackLogout();
			resetUser();

			// Revoke refresh token on server and clear all tokens from localStorage
			await logout();

			if (typeof window !== "undefined") {
				router.push("/");
			}
		} catch (error) {
			console.error("Error during logout:", error);
			await logout();
			router.push("/");
		}
	}, [router]);

	const handleViewAllSharedChats = useCallback(() => {
		setActiveSlideoutPanel((prev) => (prev === "shared" ? null : "shared"));
	}, []);

	const handleViewAllPrivateChats = useCallback(() => {
		setActiveSlideoutPanel((prev) => (prev === "private" ? null : "private"));
	}, []);

	// Delete handlers
	const confirmDeleteChat = useCallback(async () => {
		if (!chatToDelete) return;
		setIsDeletingChat(true);
		try {
			await deleteThread(chatToDelete.id);
			queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
			if (currentChatId === chatToDelete.id) {
				resetCurrentThread();
				const isOutOfSync = currentThreadState.id !== null && !params?.chat_id;
				if (isOutOfSync) {
					window.history.replaceState(null, "", `/dashboard/${searchSpaceId}/new-chat`);
					setChatResetKey((k) => k + 1);
				} else {
					router.push(`/dashboard/${searchSpaceId}/new-chat`);
				}
			}
		} catch (error) {
			console.error("Error deleting thread:", error);
		} finally {
			setIsDeletingChat(false);
			setShowDeleteChatDialog(false);
			setChatToDelete(null);
		}
	}, [
		chatToDelete,
		queryClient,
		searchSpaceId,
		resetCurrentThread,
		currentChatId,
		currentThreadState.id,
		params?.chat_id,
		router,
	]);

	// Rename handler
	const confirmRenameChat = useCallback(async () => {
		if (!chatToRename || !newChatTitle.trim()) return;
		setIsRenamingChat(true);
		try {
			await updateThread(chatToRename.id, { title: newChatTitle.trim() });
			toast.success(tSidebar("chat_renamed") || "Chat renamed");
			queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
			queryClient.invalidateQueries({ queryKey: ["all-threads", searchSpaceId] });
			queryClient.invalidateQueries({ queryKey: ["search-threads", searchSpaceId] });
		} catch (error) {
			console.error("Error renaming thread:", error);
			toast.error(tSidebar("error_renaming_chat") || "Failed to rename chat");
		} finally {
			setIsRenamingChat(false);
			setShowRenameChatDialog(false);
			setChatToRename(null);
			setNewChatTitle("");
		}
	}, [chatToRename, newChatTitle, queryClient, searchSpaceId, tSidebar]);

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
				onChatRename={handleChatRename}
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
				theme={theme}
				setTheme={setTheme}
				isChatPage={isChatPage}
				isLoadingChats={isLoadingThreads}
				activeSlideoutPanel={activeSlideoutPanel}
				onSlideoutPanelChange={setActiveSlideoutPanel}
				inbox={{
					isOpen: isInboxSidebarOpen,
					totalUnreadCount,
					comments: {
						items: commentsInbox.inboxItems,
						unreadCount: commentsInbox.unreadCount,
						loading: commentsInbox.loading,
						loadingMore: commentsInbox.loadingMore,
						hasMore: commentsInbox.hasMore,
						loadMore: commentsInbox.loadMore,
						markAsRead: commentsInbox.markAsRead,
						markAllAsRead: commentsInbox.markAllAsRead,
					},
					status: {
						items: statusInbox.inboxItems,
						unreadCount: statusInbox.unreadCount,
						loading: statusInbox.loading,
						loadingMore: statusInbox.loadingMore,
						hasMore: statusInbox.hasMore,
						loadMore: statusInbox.loadMore,
						markAsRead: statusInbox.markAsRead,
						markAllAsRead: statusInbox.markAllAsRead,
					},
				}}
				allSharedChatsPanel={{
					searchSpaceId,
				}}
				allPrivateChatsPanel={{
					searchSpaceId,
				}}
				documentsPanel={{
					open: isDocumentsSidebarOpen,
					onOpenChange: setIsDocumentsSidebarOpen,
					isDocked: isDocumentsDocked,
					onDockedChange: setIsDocumentsDocked,
				}}
				onTabSwitch={handleTabSwitch}
			>
				<Fragment key={chatResetKey}>{children}</Fragment>
			</LayoutShell>

			{/* Delete Chat Dialog */}
			<AlertDialog open={showDeleteChatDialog} onOpenChange={setShowDeleteChatDialog}>
				<AlertDialogContent className="sm:max-w-md">
					<AlertDialogHeader>
						<AlertDialogTitle>{t("delete_chat")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("delete_chat_confirm")} <span className="font-medium">{chatToDelete?.name}</span>?{" "}
							{t("action_cannot_undone")}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isDeletingChat}>{tCommon("cancel")}</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								confirmDeleteChat();
							}}
							disabled={isDeletingChat}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90 gap-2"
						>
							{isDeletingChat ? <Spinner size="sm" /> : tCommon("delete")}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			{/* Rename Chat Dialog */}
			<Dialog open={showRenameChatDialog} onOpenChange={setShowRenameChatDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<span>{tSidebar("rename_chat") || "Rename Chat"}</span>
						</DialogTitle>
						<DialogDescription>
							{tSidebar("rename_chat_description") || "Enter a new name for this conversation."}
						</DialogDescription>
					</DialogHeader>
					<Input
						value={newChatTitle}
						onChange={(e) => setNewChatTitle(e.target.value)}
						placeholder={tSidebar("chat_title_placeholder") || "Chat title"}
						onKeyDown={(e) => {
							if (e.key === "Enter" && !isRenamingChat && newChatTitle.trim()) {
								confirmRenameChat();
							}
						}}
					/>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="secondary"
							onClick={() => setShowRenameChatDialog(false)}
							disabled={isRenamingChat}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							onClick={confirmRenameChat}
							disabled={isRenamingChat || !newChatTitle.trim()}
							className="gap-2"
						>
							{isRenamingChat ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									{tSidebar("renaming") || "Renaming"}
								</>
							) : (
								tSidebar("rename") || "Rename"
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete Search Space Dialog */}
			<AlertDialog open={showDeleteSearchSpaceDialog} onOpenChange={setShowDeleteSearchSpaceDialog}>
				<AlertDialogContent className="sm:max-w-md">
					<AlertDialogHeader>
						<AlertDialogTitle>{t("delete_search_space")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("delete_space_confirm", { name: searchSpaceToDelete?.name || "" })}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isDeletingSearchSpace}>
							{tCommon("cancel")}
						</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								confirmDeleteSearchSpace();
							}}
							disabled={isDeletingSearchSpace}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90 gap-2"
						>
							{isDeletingSearchSpace ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									{t("deleting")}
								</>
							) : (
								tCommon("delete")
							)}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			{/* Leave Search Space Dialog */}
			<AlertDialog open={showLeaveSearchSpaceDialog} onOpenChange={setShowLeaveSearchSpaceDialog}>
				<AlertDialogContent className="sm:max-w-md">
					<AlertDialogHeader>
						<AlertDialogTitle>{t("leave_title")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("leave_confirm", { name: searchSpaceToLeave?.name || "" })}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isLeavingSearchSpace}>
							{tCommon("cancel")}
						</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								confirmLeaveSearchSpace();
							}}
							disabled={isLeavingSearchSpace}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90 gap-2"
						>
							{isLeavingSearchSpace ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									{t("leaving")}
								</>
							) : (
								t("leave")
							)}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			{/* Create Search Space Dialog */}
			<CreateSearchSpaceDialog
				open={isCreateSearchSpaceDialogOpen}
				onOpenChange={setIsCreateSearchSpaceDialogOpen}
			/>

			{/* Settings Dialogs */}
			<SearchSpaceSettingsDialog searchSpaceId={Number(searchSpaceId)} />
			<UserSettingsDialog />
			<TeamDialog searchSpaceId={Number(searchSpaceId)} />
			<MorePagesDialog />
		</>
	);
}
