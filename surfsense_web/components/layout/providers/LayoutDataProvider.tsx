"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { AlarmClock, AlertTriangle, Boxes, SquareTerminal } from "lucide-react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { currentThreadAtom, resetCurrentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import { announcementsDialogAtom } from "@/atoms/layout/dialogs.atom";
import { removeChatTabAtom, syncChatTabAtom, type Tab } from "@/atoms/tabs/tabs.atom";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { deleteWorkspaceMutationAtom } from "@/atoms/workspaces/workspace-mutation.atoms";
import { workspacesAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { ActionLogDialog } from "@/components/agent-action-log/action-log-dialog";
import { AnnouncementSpotlight } from "@/components/announcements/AnnouncementSpotlight";
import { AnnouncementsDialog } from "@/components/announcements/AnnouncementsDialog";
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
import { useActivateChatThread } from "@/hooks/use-activate-chat-thread";
import { useAnnouncements } from "@/hooks/use-announcements";
import { useInbox } from "@/hooks/use-inbox";
import { useArchiveThread, useDeleteThread, useRenameThread } from "@/hooks/use-thread-mutations";
import { notificationsApiService } from "@/lib/apis/notifications-api.service";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { getLoginPath, logout } from "@/lib/auth-utils";
import { fetchThreads } from "@/lib/chat/thread-persistence";
import { resetUser, trackLogout } from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import type { ChatItem, NavItem, Workspace } from "../types/layout.types";
import { CreateWorkspaceDialog } from "../ui/dialogs";
import { LayoutShell } from "../ui/shell";

interface LayoutDataProviderProps {
	workspaceId: string;
	children: React.ReactNode;
}

export function LayoutDataProvider({ workspaceId, children }: LayoutDataProviderProps) {
	const t = useTranslations("dashboard");
	const tCommon = useTranslations("common");
	const tSidebar = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const pathname = usePathname();
	const { theme, setTheme } = useTheme();

	// Announcements
	const { unreadCount: announcementUnreadCount } = useAnnouncements();

	// Atoms
	const { data: user } = useAtomValue(currentUserAtom);
	const {
		data: workspacesData,
		refetch: refetchWorkspaces,
		isSuccess: workspacesLoaded,
	} = useAtomValue(workspacesAtom);
	const { mutateAsync: deleteWorkspace } = useAtomValue(deleteWorkspaceMutationAtom);
	const currentThreadState = useAtomValue(currentThreadAtom);
	const resetCurrentThread = useSetAtom(resetCurrentThreadAtom);
	const syncChatTab = useSetAtom(syncChatTabAtom);
	const removeChatTab = useSetAtom(removeChatTabAtom);
	const { activateChatThread, prefetchChatThread } = useActivateChatThread();
	const { mutateAsync: archiveThread } = useArchiveThread(workspaceId);
	const { mutateAsync: deleteThread } = useDeleteThread(workspaceId);
	const { mutateAsync: renameThread } = useRenameThread(workspaceId);

	// Key used to force-remount the page component (e.g. after deleting the active chat
	// when the router is out of sync due to replaceState)
	const [chatResetKey, setChatResetKey] = useState(0);

	// Current IDs from URL, with fallback to atom for replaceState updates
	const currentChatId = params?.chat_id
		? Number(Array.isArray(params.chat_id) ? params.chat_id[0] : params.chat_id)
		: currentThreadState.id;

	// Fetch current workspace as a fallback for the selector while the full list catches up.
	const { data: currentWorkspace } = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId),
		queryFn: () => workspacesApiService.getWorkspace({ id: Number(workspaceId) }),
		enabled: !!workspaceId,
	});

	// Fetch recent threads for the sidebar.
	const { data: threadsData, isPending: isLoadingThreads } = useQuery({
		queryKey: ["threads", workspaceId, { limit: 6 }],
		queryFn: () => fetchThreads(Number(workspaceId), 6),
		enabled: !!workspaceId,
	});

	// Search space dialog state
	const [isCreateWorkspaceDialogOpen, setIsCreateWorkspaceDialogOpen] = useState(false);

	const userId = user?.id ? String(user.id) : null;
	const numericSpaceId = Number(workspaceId) || null;

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

	// Track seen notification IDs to detect new insufficient_credits notifications
	const seenCreditNotifications = useRef<Set<number>>(new Set());
	const isInitialLoad = useRef(true);

	// Effect to show toast for new insufficient_credits notifications
	useEffect(() => {
		if (statusInbox.loading) return;

		const creditNotifications = statusInbox.inboxItems.filter(
			(item) => item.type === "insufficient_credits"
		);

		if (isInitialLoad.current) {
			for (const notification of creditNotifications) {
				seenCreditNotifications.current.add(notification.id);
			}
			isInitialLoad.current = false;
			return;
		}

		const newNotifications = creditNotifications.filter(
			(notification) => !seenCreditNotifications.current.has(notification.id)
		);

		for (const notification of newNotifications) {
			seenCreditNotifications.current.add(notification.id);

			toast.error(notification.title, {
				description: notification.message,
				duration: 8000,
				icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
				action: {
					label: "Buy credits",
					onClick: () => router.push(`/dashboard/${workspaceId}/buy-more`),
				},
			});
		}
	}, [statusInbox.inboxItems, statusInbox.loading, workspaceId, router]);

	// Delete dialogs state
	const [showDeleteChatDialog, setShowDeleteChatDialog] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; name: string } | null>(null);
	const [isDeletingChat, setIsDeletingChat] = useState(false);

	// Rename dialog state
	const [showRenameChatDialog, setShowRenameChatDialog] = useState(false);
	const [chatToRename, setChatToRename] = useState<{ id: number; name: string } | null>(null);
	const [newChatTitle, setNewChatTitle] = useState("");
	const [isRenamingChat, setIsRenamingChat] = useState(false);

	// Delete/Leave workspace dialog state
	const [showDeleteWorkspaceDialog, setShowDeleteWorkspaceDialog] = useState(false);
	const [showLeaveWorkspaceDialog, setShowLeaveWorkspaceDialog] = useState(false);
	const [workspaceToDelete, setWorkspaceToDelete] = useState<Workspace | null>(null);
	const [workspaceToLeave, setWorkspaceToLeave] = useState<Workspace | null>(null);
	const [isDeletingWorkspace, setIsDeletingWorkspace] = useState(false);
	const [isLeavingWorkspace, setIsLeavingWorkspace] = useState(false);

	const workspaces: Workspace[] = useMemo(() => {
		if (!workspacesData || !Array.isArray(workspacesData)) return [];
		return workspacesData.map((space) => ({
			id: space.id,
			name: space.name,
			description: space.description,
			isOwner: space.is_owner,
			memberCount: space.member_count || 0,
			createdAt: space.created_at,
		}));
	}, [workspacesData]);

	// Find active workspace from list, falling back to the route-scoped detail query.
	const activeWorkspace: Workspace | null = useMemo(() => {
		if (!workspaceId) return null;
		const workspaceIdNumber = Number(workspaceId);
		const listedSpace = workspaces.find((s) => s.id === workspaceIdNumber);
		if (listedSpace) return listedSpace;
		if (!currentWorkspace || currentWorkspace.id !== workspaceIdNumber) return null;
		return {
			id: currentWorkspace.id,
			name: currentWorkspace.name,
			description: currentWorkspace.description,
			isOwner: false,
			memberCount: 0,
			createdAt: currentWorkspace.created_at,
		};
	}, [currentWorkspace, workspaceId, workspaces]);

	// Safety redirect: if the current workspace is no longer in the user's list
	// (e.g. deleted by background task, membership revoked), redirect to a valid space.
	useEffect(() => {
		if (!workspacesLoaded || !workspaceId || isDeletingWorkspace || isLeavingWorkspace) return;
		if (workspaces.length > 0 && !activeWorkspace) {
			router.replace(`/dashboard/${workspaces[0].id}/new-chat`);
		} else if (workspaces.length === 0 && workspacesLoaded && !activeWorkspace) {
			router.replace("/dashboard");
		}
	}, [
		workspacesLoaded,
		workspaceId,
		workspaces,
		activeWorkspace,
		isDeletingWorkspace,
		isLeavingWorkspace,
		router,
	]);

	// Sync current chat route with tab state
	useEffect(() => {
		const chatId = currentChatId ?? null;
		const chatUrl = chatId
			? `/dashboard/${workspaceId}/new-chat/${chatId}`
			: `/dashboard/${workspaceId}/new-chat`;
		const thread = threadsData?.threads?.find((t) => t.id === chatId);
		syncChatTab({
			chatId,
			// Avoid overwriting live SSE-updated tab titles with fallback values.
			title: chatId ? (thread?.title ?? undefined) : "New Chat",
			chatUrl,
			workspaceId: Number(workspaceId),
			...(thread?.visibility !== undefined ? { visibility: thread.visibility } : {}),
		});
	}, [currentChatId, workspaceId, threadsData?.threads, syncChatTab]);

	const chats = useMemo(() => {
		if (!threadsData?.threads) return [];

		return threadsData.threads.map<ChatItem>((thread) => ({
			id: thread.id,
			name: thread.title || `Chat ${thread.id}`,
			url: `/dashboard/${workspaceId}/new-chat/${thread.id}`,
			visibility: thread.visibility,
			isOwnThread: thread.is_own_thread,
			archived: thread.archived,
		}));
	}, [threadsData, workspaceId]);

	// Navigation items
	// Automations and Artifacts are rendered explicitly below "New chat"
	// in the sidebar. Documents is embedded below Recents; notifications and
	// announcements live in the avatar rail/dropdown.
	const isAutomationsActive = pathname?.includes("/automations") === true;
	const isArtifactsActive = pathname?.endsWith("/artifacts") === true;
	const isPlaygroundRoute = pathname?.includes("/playground") === true;
	const navItems: NavItem[] = useMemo(
		() =>
			(
				[
					{
						title: "Automations",
						url: `/dashboard/${workspaceId}/automations`,
						icon: AlarmClock,
						isActive: isAutomationsActive,
					},
					{
						title: "Artifacts",
						url: `/dashboard/${workspaceId}/artifacts`,
						icon: Boxes,
						isActive: isArtifactsActive,
					},
					{
						title: "Playground",
						url: `/dashboard/${workspaceId}/playground`,
						icon: SquareTerminal,
						isActive: isPlaygroundRoute,
					},
				] as (NavItem | null)[]
			).filter((item): item is NavItem => item !== null),
		[workspaceId, isAutomationsActive, isArtifactsActive, isPlaygroundRoute]
	);

	// Handlers
	const handleWorkspaceSelect = useCallback(
		(id: number) => {
			router.push(`/dashboard/${id}/new-chat`);
		},
		[router]
	);

	const handleAddWorkspace = useCallback(() => {
		setIsCreateWorkspaceDialogOpen(true);
	}, []);

	const setAnnouncementsDialog = useSetAtom(announcementsDialogAtom);

	const handleUserSettings = useCallback(() => {
		router.push(`/dashboard/${workspaceId}/user-settings/profile`);
	}, [router, workspaceId]);

	const handleAnnouncements = useCallback(() => {
		setAnnouncementsDialog(true);
	}, [setAnnouncementsDialog]);

	const handleWorkspaceSettings = useCallback(
		(space: Workspace) => {
			router.push(`/dashboard/${space.id}/workspace-settings`);
		},
		[router]
	);

	const handleWorkspaceDeleteClick = useCallback((space: Workspace) => {
		// If user is owner, show delete dialog; otherwise show leave dialog
		if (space.isOwner) {
			setWorkspaceToDelete(space);
			setShowDeleteWorkspaceDialog(true);
		} else {
			setWorkspaceToLeave(space);
			setShowLeaveWorkspaceDialog(true);
		}
	}, []);

	const confirmDeleteWorkspace = useCallback(async () => {
		if (!workspaceToDelete) return;
		setIsDeletingWorkspace(true);
		try {
			await deleteWorkspace({ id: workspaceToDelete.id });

			const isCurrentSpace = Number(workspaceId) === workspaceToDelete.id;

			// Await refetch so we have the freshest list (backend now hides [DELETING] spaces)
			const result = await refetchWorkspaces();
			const updatedSpaces = (result.data ?? []).filter((s) => s.id !== workspaceToDelete.id);

			if (isCurrentSpace) {
				if (updatedSpaces.length > 0) {
					router.push(`/dashboard/${updatedSpaces[0].id}/new-chat`);
				} else {
					router.push("/dashboard");
				}
			}
		} catch (error) {
			console.error("Error deleting workspace:", error);
			toast.error(
				t.has("delete_space_error") ? t("delete_space_error") : "Failed to delete workspace"
			);
		} finally {
			setIsDeletingWorkspace(false);
			setShowDeleteWorkspaceDialog(false);
			setWorkspaceToDelete(null);
		}
	}, [workspaceToDelete, deleteWorkspace, refetchWorkspaces, workspaceId, router, t]);

	const confirmLeaveWorkspace = useCallback(async () => {
		if (!workspaceToLeave) return;
		setIsLeavingWorkspace(true);
		try {
			await workspacesApiService.leaveWorkspace(workspaceToLeave.id);

			const isCurrentSpace = Number(workspaceId) === workspaceToLeave.id;

			const result = await refetchWorkspaces();
			const updatedSpaces = (result.data ?? []).filter((s) => s.id !== workspaceToLeave.id);

			if (isCurrentSpace) {
				if (updatedSpaces.length > 0) {
					router.push(`/dashboard/${updatedSpaces[0].id}/new-chat`);
				} else {
					router.push("/dashboard");
				}
			}
		} catch (error) {
			console.error("Error leaving workspace:", error);
			toast.error(t.has("leave_error") ? t("leave_error") : "Failed to leave workspace");
		} finally {
			setIsLeavingWorkspace(false);
			setShowLeaveWorkspaceDialog(false);
			setWorkspaceToLeave(null);
		}
	}, [workspaceToLeave, refetchWorkspaces, workspaceId, router, t]);

	const handleTabSwitch = useCallback(
		(tab: Tab) => {
			if (tab.type === "chat") {
				activateChatThread({
					id: tab.chatId ?? null,
					title: tab.title,
					url: tab.chatUrl,
					workspaceId: tab.workspaceId ?? workspaceId,
					...(tab.visibility !== undefined ? { visibility: tab.visibility } : {}),
					...(tab.hasComments !== undefined ? { hasComments: tab.hasComments } : {}),
				});
			}
			// Document tabs are handled in-place by LayoutShell — no navigation needed
		},
		[activateChatThread, workspaceId]
	);

	const handleTabPrefetch = useCallback(
		(tab: Tab) => {
			if (tab.type === "chat") {
				prefetchChatThread(tab.chatId);
			}
		},
		[prefetchChatThread]
	);

	const handleChatPrefetch = useCallback(
		(chat: ChatItem) => {
			prefetchChatThread(chat.id);
		},
		[prefetchChatThread]
	);

	const handleNavItemClick = useCallback(
		(item: NavItem) => {
			router.push(item.url);
		},
		[router]
	);

	const handleNewChat = useCallback(() => {
		// Check if router is out of sync (thread created via replaceState but params don't have chat_id)
		const isOutOfSync = currentThreadState.id !== null && !params?.chat_id;

		if (isOutOfSync) {
			resetCurrentThread();
			// Immediately set the browser URL so the page remounts with a clean /new-chat path
			window.history.replaceState(null, "", `/dashboard/${workspaceId}/new-chat`);
			// Force-remount the page component to reset all React state synchronously
			setChatResetKey((k) => k + 1);
			// Sync Next.js router internals so useParams/usePathname stay correct going forward
			router.replace(`/dashboard/${workspaceId}/new-chat`);
		} else {
			router.push(`/dashboard/${workspaceId}/new-chat`);
		}
	}, [router, workspaceId, currentThreadState.id, params?.chat_id, resetCurrentThread]);

	const handleChatSelect = useCallback(
		(chat: ChatItem) => {
			activateChatThread({
				id: chat.id,
				title: chat.name,
				url: chat.url,
				workspaceId,
				...(chat.visibility !== undefined ? { visibility: chat.visibility } : {}),
			});
		},
		[activateChatThread, workspaceId]
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
				await archiveThread({ threadId: chat.id, archived: newArchivedState });
				toast.success(successMessage);
			} catch (error) {
				console.error("Error archiving thread:", error);
				toast.error(tSidebar("error_archiving_chat") || "Failed to archive chat");
			}
		},
		[archiveThread, tSidebar]
	);

	const handleSettings = useCallback(() => {
		router.push(`/dashboard/${workspaceId}/workspace-settings`);
	}, [router, workspaceId]);

	const handleManageMembers = useCallback(() => {
		router.push(`/dashboard/${workspaceId}/team`);
	}, [router, workspaceId]);

	const handleLogout = useCallback(async () => {
		try {
			trackLogout();
			resetUser();

			// Revoke refresh token on server and clear all tokens from localStorage
			await logout();

			if (typeof window !== "undefined") {
				router.push(getLoginPath());
			}
		} catch (error) {
			console.error("Error during logout:", error);
			await logout();
			router.push(getLoginPath());
		}
	}, [router]);

	// Delete handlers
	const confirmDeleteChat = useCallback(async () => {
		if (!chatToDelete) return;
		setIsDeletingChat(true);
		try {
			await deleteThread({ threadId: chatToDelete.id });
			const fallbackTab = removeChatTab(chatToDelete.id);
			if (currentChatId === chatToDelete.id) {
				resetCurrentThread();
				if (fallbackTab?.type === "chat" && fallbackTab.chatUrl) {
					activateChatThread({
						id: fallbackTab.chatId ?? null,
						title: fallbackTab.title,
						url: fallbackTab.chatUrl,
						workspaceId: fallbackTab.workspaceId ?? workspaceId,
						...(fallbackTab.visibility !== undefined ? { visibility: fallbackTab.visibility } : {}),
						...(fallbackTab.hasComments !== undefined
							? { hasComments: fallbackTab.hasComments }
							: {}),
					});
				} else {
					const isOutOfSync = currentThreadState.id !== null && !params?.chat_id;
					if (isOutOfSync) {
						window.history.replaceState(null, "", `/dashboard/${workspaceId}/new-chat`);
						setChatResetKey((k) => k + 1);
					} else {
						router.push(`/dashboard/${workspaceId}/new-chat`);
					}
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
		deleteThread,
		workspaceId,
		resetCurrentThread,
		currentChatId,
		currentThreadState.id,
		params?.chat_id,
		router,
		removeChatTab,
		activateChatThread,
	]);

	// Rename handler
	const confirmRenameChat = useCallback(async () => {
		if (!chatToRename || !newChatTitle.trim()) return;
		setIsRenamingChat(true);
		try {
			await renameThread({
				threadId: chatToRename.id,
				title: newChatTitle.trim(),
				previousTitle: chatToRename.name,
			});
			toast.success(tSidebar("chat_renamed") || "Chat renamed");
		} catch (error) {
			console.error("Error renaming thread:", error);
			toast.error(tSidebar("error_renaming_chat") || "Failed to rename chat");
		} finally {
			setIsRenamingChat(false);
			setShowRenameChatDialog(false);
			setChatToRename(null);
			setNewChatTitle("");
		}
	}, [chatToRename, newChatTitle, renameThread, tSidebar]);

	// Detect if we're on the chat page (needs overflow-hidden for chat's own scroll)
	const isChatPage = pathname?.includes("/new-chat") ?? false;
	const isUserSettingsPage = pathname?.includes("/user-settings") === true;
	const isWorkspaceSettingsPage = pathname?.includes("/workspace-settings") === true;
	const isTeamPage = pathname?.endsWith("/team") === true;
	const isAutomationsPage = pathname?.includes("/automations") === true;
	const isArtifactsPage = pathname?.endsWith("/artifacts") === true;
	const isPlaygroundPage = pathname?.includes("/playground") === true;
	const isAllChatsPage = pathname?.endsWith("/chats") === true;
	const handleViewAllChats = useCallback(() => {
		router.push(
			isAllChatsPage ? `/dashboard/${workspaceId}/new-chat` : `/dashboard/${workspaceId}/chats`
		);
	}, [isAllChatsPage, router, workspaceId]);
	const useWorkspacePanel =
		pathname?.endsWith("/buy-more") === true ||
		pathname?.endsWith("/earn-credits") === true ||
		pathname?.endsWith("/more-pages") === true ||
		isUserSettingsPage ||
		isWorkspaceSettingsPage ||
		isTeamPage ||
		isAutomationsPage ||
		isArtifactsPage ||
		isPlaygroundPage ||
		isAllChatsPage;

	return (
		<>
			<LayoutShell
				workspaces={workspaces}
				activeWorkspaceId={Number(workspaceId)}
				onWorkspaceSelect={handleWorkspaceSelect}
				onWorkspaceDelete={handleWorkspaceDeleteClick}
				onWorkspaceSettings={handleWorkspaceSettings}
				onAddWorkspace={handleAddWorkspace}
				workspace={activeWorkspace}
				navItems={navItems}
				onNavItemClick={handleNavItemClick}
				chats={chats}
				activeChatId={currentChatId}
				onNewChat={handleNewChat}
				onChatSelect={handleChatSelect}
				onChatPrefetch={handleChatPrefetch}
				onChatRename={handleChatRename}
				onChatDelete={handleChatDelete}
				onChatArchive={handleChatArchive}
				onViewAllChats={handleViewAllChats}
				user={{
					email: user?.email || "",
					name: user?.display_name || user?.email?.split("@")[0],
					avatarUrl: user?.avatar_url || undefined,
				}}
				onSettings={handleSettings}
				onManageMembers={handleManageMembers}
				onUserSettings={handleUserSettings}
				onAnnouncements={handleAnnouncements}
				announcementUnreadCount={announcementUnreadCount}
				onLogout={handleLogout}
				theme={theme}
				setTheme={setTheme}
				isChatPage={isChatPage}
				isAllChatsPage={isAllChatsPage}
				useWorkspacePanel={useWorkspacePanel}
				workspacePanelViewportClassName={
					isUserSettingsPage ||
					isWorkspaceSettingsPage ||
					isTeamPage ||
					isAutomationsPage ||
					isArtifactsPage ||
					isPlaygroundPage ||
					isAllChatsPage
						? "items-start justify-center px-6 py-8 md:px-10 md:pb-10 md:pt-16"
						: undefined
				}
				workspacePanelContentClassName={
					useWorkspacePanel ? "max-w-5xl select-none" : undefined
				}
				isLoadingChats={isLoadingThreads}
				notifications={{
					totalUnreadCount,
					comments: {
						items: commentsInbox.inboxItems,
						unreadCount: commentsInbox.unreadCount,
						totalCount: commentsInbox.totalCount,
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
						totalCount: statusInbox.totalCount,
						loading: statusInbox.loading,
						loadingMore: statusInbox.loadingMore,
						hasMore: statusInbox.hasMore,
						loadMore: statusInbox.loadMore,
						markAsRead: statusInbox.markAsRead,
						markAllAsRead: statusInbox.markAllAsRead,
					},
				}}
				onTabSwitch={handleTabSwitch}
				onTabPrefetch={handleTabPrefetch}
			>
				<Fragment key={chatResetKey}>{children}</Fragment>
			</LayoutShell>

			{/* Delete Chat Dialog */}
			<AlertDialog open={showDeleteChatDialog} onOpenChange={setShowDeleteChatDialog}>
				<AlertDialogContent className="sm:max-w-md">
					<AlertDialogHeader>
						<AlertDialogTitle>{t("delete_chat")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("delete_chat_confirm")}{" "}
							<span className="font-medium break-all">{chatToDelete?.name}</span>?{" "}
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
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90 items-center justify-center"
						>
							<span className={isDeletingChat ? "opacity-0" : ""}>{tCommon("delete")}</span>
							{isDeletingChat && <Spinner size="sm" className="absolute" />}
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
					<DialogFooter className="flex sm:justify-end">
						<Button
							variant="secondary"
							onClick={() => setShowRenameChatDialog(false)}
							disabled={isRenamingChat}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							onClick={confirmRenameChat}
							disabled={
								isRenamingChat || !newChatTitle.trim() || newChatTitle.trim() === chatToRename?.name
							}
							className="relative"
						>
							<span className={isRenamingChat ? "opacity-0" : ""}>
								{tSidebar("rename") || "Rename"}
							</span>
							{isRenamingChat && (
								<Spinner
									size="sm"
									className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
								/>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete Workspace Dialog */}
			<AlertDialog open={showDeleteWorkspaceDialog} onOpenChange={setShowDeleteWorkspaceDialog}>
				<AlertDialogContent className="sm:max-w-md">
					<AlertDialogHeader>
						<AlertDialogTitle>{t("delete_workspace")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("delete_space_confirm", { name: workspaceToDelete?.name || "" })}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isDeletingWorkspace}>
							{tCommon("cancel")}
						</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								confirmDeleteWorkspace();
							}}
							disabled={isDeletingWorkspace}
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							<span className={isDeletingWorkspace ? "opacity-0" : ""}>{tCommon("delete")}</span>
							{isDeletingWorkspace && <Spinner size="sm" className="absolute" />}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			{/* Leave Workspace Dialog */}
			<AlertDialog open={showLeaveWorkspaceDialog} onOpenChange={setShowLeaveWorkspaceDialog}>
				<AlertDialogContent className="sm:max-w-md">
					<AlertDialogHeader>
						<AlertDialogTitle>{t("leave_title")}</AlertDialogTitle>
						<AlertDialogDescription>
							{t("leave_confirm", { name: workspaceToLeave?.name || "" })}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isLeavingWorkspace}>{tCommon("cancel")}</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								confirmLeaveWorkspace();
							}}
							disabled={isLeavingWorkspace}
							className="relative bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							<span className={isLeavingWorkspace ? "opacity-0" : ""}>{t("leave")}</span>
							{isLeavingWorkspace && <Spinner size="sm" className="absolute" />}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			{/* Create Workspace Dialog */}
			<CreateWorkspaceDialog
				open={isCreateWorkspaceDialogOpen}
				onOpenChange={setIsCreateWorkspaceDialogOpen}
			/>

			<AnnouncementsDialog />
			<AnnouncementSpotlight />

			{/* Agent action log + revert dialog */}
			<ActionLogDialog />
		</>
	);
}
