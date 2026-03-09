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
import { deleteSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { searchSpacesAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
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
import { isPageLimitExceededMetadata } from "@/contracts/types/inbox.types";
import { useAnnouncements } from "@/hooks/use-announcements";
import { useDocumentsProcessing } from "@/hooks/use-documents-processing";
import { useInbox } from "@/hooks/use-inbox";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { logout } from "@/lib/auth-utils";
import { deleteThread, fetchThreads, updateThread } from "@/lib/chat/thread-persistence";
import { cleanupElectric } from "@/lib/electric/client";
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

	// Announcements
	const { unreadCount: announcementUnreadCount } = useAnnouncements();

	// Atoms
	const { data: user } = useAtomValue(currentUserAtom);
	const { data: searchSpacesData, refetch: refetchSearchSpaces } = useAtomValue(searchSpacesAtom);
	const { mutateAsync: deleteSearchSpace } = useAtomValue(deleteSearchSpaceMutationAtom);
	const currentThreadState = useAtomValue(currentThreadAtom);
	const resetCurrentThread = useSetAtom(resetCurrentThreadAtom);

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

	// Separate sidebar states for shared and private chats
	const [isAllSharedChatsSidebarOpen, setIsAllSharedChatsSidebarOpen] = useState(false);
	const [isAllPrivateChatsSidebarOpen, setIsAllPrivateChatsSidebarOpen] = useState(false);

	// Inbox sidebar state
	const [isInboxSidebarOpen, setIsInboxSidebarOpen] = useState(false);
	const [isInboxDocked, setIsInboxDocked] = useState(false);

	// Documents sidebar state (shared atom so Composer can toggle it)
	const [isDocumentsSidebarOpen, setIsDocumentsSidebarOpen] = useAtom(documentsSidebarOpenAtom);

	// Announcements sidebar state
	const [isAnnouncementsSidebarOpen, setIsAnnouncementsSidebarOpen] = useState(false);

	// Search space dialog state
	const [isCreateSearchSpaceDialogOpen, setIsCreateSearchSpaceDialogOpen] = useState(false);

	// Per-tab inbox hooks — each has independent API loading, pagination,
	// and Electric live queries. The Electric sync shape is shared (client-level cache).
	const userId = user?.id ? String(user.id) : null;
	const numericSpaceId = Number(searchSpaceId) || null;

	const commentsInbox = useInbox(userId, numericSpaceId, "comments");
	const statusInbox = useInbox(userId, numericSpaceId, "status");

	const totalUnreadCount = commentsInbox.unreadCount + statusInbox.unreadCount;

	// Document processing status — drives sidebar status indicator (spinner / check / error)
	const documentsProcessingStatus = useDocumentsProcessing(numericSpaceId);

	// Track seen notification IDs to detect new page_limit_exceeded notifications
	const seenPageLimitNotifications = useRef<Set<number>>(new Set());
	const isInitialLoad = useRef(true);

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
	}, [statusInbox.inboxItems, statusInbox.loading, searchSpaceId, router]);

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
				url: "#inbox",
				icon: Inbox,
				isActive: isInboxSidebarOpen,
				badge: totalUnreadCount > 0 ? formatInboxCount(totalUnreadCount) : undefined,
			},
			{
				title: "Documents",
				url: "#documents",
				icon: SquareLibrary,
				isActive: isDocumentsSidebarOpen,
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
			isInboxSidebarOpen,
			isDocumentsSidebarOpen,
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

	const handleUserSettings = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/user-settings?tab=profile`);
	}, [router, searchSpaceId]);

	const handleSearchSpaceSettings = useCallback(
		(space: SearchSpace) => {
			router.push(`/dashboard/${space.id}/settings?tab=general`);
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
			if (item.url === "#inbox") {
				setIsInboxSidebarOpen((prev) => {
					if (!prev) {
						setIsAllSharedChatsSidebarOpen(false);
						setIsAllPrivateChatsSidebarOpen(false);
						setIsDocumentsSidebarOpen(false);
						setIsAnnouncementsSidebarOpen(false);
					}
					return !prev;
				});
				return;
			}
			if (item.url === "#documents") {
				setIsDocumentsSidebarOpen((prev) => {
					if (!prev) {
						setIsInboxSidebarOpen(false);
						setIsAllSharedChatsSidebarOpen(false);
						setIsAllPrivateChatsSidebarOpen(false);
						setIsAnnouncementsSidebarOpen(false);
					}
					return !prev;
				});
				return;
			}
			if (item.url === "#announcements") {
				setIsAnnouncementsSidebarOpen((prev) => {
					if (!prev) {
						setIsInboxSidebarOpen(false);
						setIsAllSharedChatsSidebarOpen(false);
						setIsAllPrivateChatsSidebarOpen(false);
						setIsDocumentsSidebarOpen(false);
					}
					return !prev;
				});
				return;
			}
			router.push(item.url);
		},
		[router, setIsDocumentsSidebarOpen]
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
		router.push(`/dashboard/${searchSpaceId}/settings?tab=general`);
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
		setIsAllSharedChatsSidebarOpen(true);
		setIsAllPrivateChatsSidebarOpen(false);
		setIsInboxSidebarOpen(false);
		setIsDocumentsSidebarOpen(false);
		setIsAnnouncementsSidebarOpen(false);
	}, [setIsDocumentsSidebarOpen]);

	const handleViewAllPrivateChats = useCallback(() => {
		setIsAllPrivateChatsSidebarOpen(true);
		setIsAllSharedChatsSidebarOpen(false);
		setIsInboxSidebarOpen(false);
		setIsDocumentsSidebarOpen(false);
		setIsAnnouncementsSidebarOpen(false);
	}, [setIsDocumentsSidebarOpen]);

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
				inbox={{
					isOpen: isInboxSidebarOpen,
					onOpenChange: setIsInboxSidebarOpen,
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
					isDocked: isInboxDocked,
					onDockedChange: setIsInboxDocked,
				}}
				announcementsPanel={{
					open: isAnnouncementsSidebarOpen,
					onOpenChange: setIsAnnouncementsSidebarOpen,
				}}
				allSharedChatsPanel={{
					open: isAllSharedChatsSidebarOpen,
					onOpenChange: setIsAllSharedChatsSidebarOpen,
					searchSpaceId,
				}}
				allPrivateChatsPanel={{
					open: isAllPrivateChatsSidebarOpen,
					onOpenChange: setIsAllPrivateChatsSidebarOpen,
					searchSpaceId,
				}}
				documentsPanel={{
					open: isDocumentsSidebarOpen,
					onOpenChange: setIsDocumentsSidebarOpen,
				}}
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
							{isDeletingChat ? (
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
		</>
	);
}
