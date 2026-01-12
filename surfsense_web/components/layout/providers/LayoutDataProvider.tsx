"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { Logs, SquareLibrary, Trash2 } from "lucide-react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useCallback, useMemo, useState } from "react";
import { hasUnsavedEditorChangesAtom, pendingEditorNavigationAtom } from "@/atoms/editor/ui.atoms";
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
import { useLogsSummary } from "@/hooks/use-logs";
import { notesApiService } from "@/lib/apis/notes-api.service";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { deleteThread, fetchThreads } from "@/lib/chat/thread-persistence";
import { resetUser, trackLogout } from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import type { ChatItem, NavItem, NoteItem, SearchSpace } from "../types/layout.types";
import { CreateSearchSpaceDialog } from "../ui/dialogs";
import { LayoutShell } from "../ui/shell";
import { AllSearchSpacesSheet } from "../ui/sheets";
import { AllChatsSidebar } from "../ui/sidebar/AllChatsSidebar";
import { AllNotesSidebar } from "../ui/sidebar/AllNotesSidebar";

interface LayoutDataProviderProps {
	searchSpaceId: string;
	children: React.ReactNode;
	breadcrumb?: React.ReactNode;
	languageSwitcher?: React.ReactNode;
}

export function LayoutDataProvider({
	searchSpaceId,
	children,
	breadcrumb,
	languageSwitcher,
}: LayoutDataProviderProps) {
	const t = useTranslations("dashboard");
	const tCommon = useTranslations("common");
	const router = useRouter();
	const params = useParams();
	const pathname = usePathname();
	const queryClient = useQueryClient();
	const { theme, setTheme } = useTheme();

	// Atoms
	const { data: user } = useAtomValue(currentUserAtom);
	const { data: searchSpacesData, refetch: refetchSearchSpaces } = useAtomValue(searchSpacesAtom);
	const { mutateAsync: deleteSearchSpace } = useAtomValue(deleteSearchSpaceMutationAtom);
	const hasUnsavedEditorChanges = useAtomValue(hasUnsavedEditorChangesAtom);
	const setPendingNavigation = useSetAtom(pendingEditorNavigationAtom);

	// Current IDs from URL
	const currentChatId = params?.chat_id
		? Number(Array.isArray(params.chat_id) ? params.chat_id[0] : params.chat_id)
		: null;
	const currentNoteId = params?.note_id
		? Number(Array.isArray(params.note_id) ? params.note_id[0] : params.note_id)
		: null;

	// Fetch current search space
	const { data: searchSpace } = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: Number(searchSpaceId) }),
		enabled: !!searchSpaceId,
	});

	// Fetch threads
	const { data: threadsData, refetch: refetchThreads } = useQuery({
		queryKey: ["threads", searchSpaceId, { limit: 4 }],
		queryFn: () => fetchThreads(Number(searchSpaceId), 4),
		enabled: !!searchSpaceId,
	});

	// Fetch notes
	const { data: notesData, refetch: refetchNotes } = useQuery({
		queryKey: ["notes", searchSpaceId],
		queryFn: () =>
			notesApiService.getNotes({
				search_space_id: Number(searchSpaceId),
				page_size: 4,
			}),
		enabled: !!searchSpaceId,
	});

	// Poll for active reindexing tasks to show inline loading indicators
	const { summary } = useLogsSummary(searchSpaceId ? Number(searchSpaceId) : 0, 24, {
		enablePolling: true,
		refetchInterval: 5000,
	});

	// Create a Set of document IDs that are currently being reindexed
	const reindexingDocumentIds = useMemo(() => {
		if (!summary?.active_tasks) return new Set<number>();
		return new Set(
			summary.active_tasks
				.filter((task) => task.document_id != null)
				.map((task) => task.document_id as number)
		);
	}, [summary?.active_tasks]);

	// All chats/notes sidebars state
	const [isAllChatsSidebarOpen, setIsAllChatsSidebarOpen] = useState(false);
	const [isAllNotesSidebarOpen, setIsAllNotesSidebarOpen] = useState(false);

	// Search space sheet and dialog state
	const [isAllSearchSpacesSheetOpen, setIsAllSearchSpacesSheetOpen] = useState(false);
	const [isCreateSearchSpaceDialogOpen, setIsCreateSearchSpaceDialogOpen] = useState(false);

	// Delete dialogs state
	const [showDeleteChatDialog, setShowDeleteChatDialog] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; name: string } | null>(null);
	const [isDeletingChat, setIsDeletingChat] = useState(false);

	const [showDeleteNoteDialog, setShowDeleteNoteDialog] = useState(false);
	const [noteToDelete, setNoteToDelete] = useState<{
		id: number;
		name: string;
		search_space_id: number;
	} | null>(null);
	const [isDeletingNote, setIsDeletingNote] = useState(false);

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

	// Transform chats
	const chats: ChatItem[] = useMemo(() => {
		if (!threadsData?.threads) return [];
		return threadsData.threads.map((thread) => ({
			id: thread.id,
			name: thread.title || `Chat ${thread.id}`,
			url: `/dashboard/${searchSpaceId}/new-chat/${thread.id}`,
		}));
	}, [threadsData, searchSpaceId]);

	// Transform notes
	const notes: NoteItem[] = useMemo(() => {
		if (!notesData?.items) return [];
		const sortedNotes = [...notesData.items].sort((a, b) => {
			const dateA = a.updated_at
				? new Date(a.updated_at).getTime()
				: new Date(a.created_at).getTime();
			const dateB = b.updated_at
				? new Date(b.updated_at).getTime()
				: new Date(b.created_at).getTime();
			return dateB - dateA;
		});
		return sortedNotes.slice(0, 4).map((note) => ({
			id: note.id,
			name: note.title,
			url: `/dashboard/${note.search_space_id}/editor/${note.id}`,
			isReindexing: reindexingDocumentIds.has(note.id),
		}));
	}, [notesData, reindexingDocumentIds]);

	// Navigation items
	const navItems: NavItem[] = useMemo(
		() => [
			{
				title: "Documents",
				url: `/dashboard/${searchSpaceId}/documents`,
				icon: SquareLibrary,
				isActive: pathname?.includes("/documents"),
			},
			{
				title: "Logs",
				url: `/dashboard/${searchSpaceId}/logs`,
				icon: Logs,
				isActive: pathname?.includes("/logs"),
			},
		],
		[searchSpaceId, pathname]
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

	const handleSeeAllSearchSpaces = useCallback(() => {
		setIsAllSearchSpacesSheetOpen(true);
	}, []);

	const handleUserSettings = useCallback(() => {
		router.push("/dashboard/user/settings");
	}, [router]);

	const handleSearchSpaceSettings = useCallback(
		(id: number) => {
			router.push(`/dashboard/${id}/settings`);
		},
		[router]
	);

	const handleDeleteSearchSpace = useCallback(
		async (id: number) => {
			await deleteSearchSpace({ id });
			refetchSearchSpaces();
			if (Number(searchSpaceId) === id && searchSpaces.length > 1) {
				const remaining = searchSpaces.filter((s) => s.id !== id);
				if (remaining.length > 0) {
					router.push(`/dashboard/${remaining[0].id}/new-chat`);
				}
			} else if (searchSpaces.length === 1) {
				router.push("/dashboard");
			}
		},
		[deleteSearchSpace, refetchSearchSpaces, searchSpaceId, searchSpaces, router]
	);

	const handleNavItemClick = useCallback(
		(item: NavItem) => {
			router.push(item.url);
		},
		[router]
	);

	const handleNewChat = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/new-chat`);
	}, [router, searchSpaceId]);

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

	const handleNoteSelect = useCallback(
		(note: NoteItem) => {
			if (hasUnsavedEditorChanges) {
				setPendingNavigation(note.url);
			} else {
				router.push(note.url);
			}
		},
		[router, hasUnsavedEditorChanges, setPendingNavigation]
	);

	const handleNoteDelete = useCallback(
		(note: NoteItem) => {
			setNoteToDelete({ id: note.id, name: note.name, search_space_id: Number(searchSpaceId) });
			setShowDeleteNoteDialog(true);
		},
		[searchSpaceId]
	);

	const handleAddNote = useCallback(() => {
		const newNoteUrl = `/dashboard/${searchSpaceId}/editor/new`;
		if (hasUnsavedEditorChanges) {
			setPendingNavigation(newNoteUrl);
		} else {
			router.push(newNoteUrl);
		}
	}, [router, searchSpaceId, hasUnsavedEditorChanges, setPendingNavigation]);

	const handleSettings = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/settings`);
	}, [router, searchSpaceId]);

	const handleManageMembers = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/team`);
	}, [router, searchSpaceId]);

	const handleLogout = useCallback(() => {
		try {
			trackLogout();
			resetUser();
			if (typeof window !== "undefined") {
				localStorage.removeItem("surfsense_bearer_token");
				router.push("/");
			}
		} catch (error) {
			console.error("Error during logout:", error);
			router.push("/");
		}
	}, [router]);

	const handleToggleTheme = useCallback(() => {
		setTheme(theme === "dark" ? "light" : "dark");
	}, [theme, setTheme]);

	const handleViewAllChats = useCallback(() => {
		setIsAllChatsSidebarOpen(true);
	}, []);

	const handleViewAllNotes = useCallback(() => {
		setIsAllNotesSidebarOpen(true);
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

	const confirmDeleteNote = useCallback(async () => {
		if (!noteToDelete) return;
		setIsDeletingNote(true);
		try {
			await notesApiService.deleteNote({
				search_space_id: noteToDelete.search_space_id,
				note_id: noteToDelete.id,
			});
			refetchNotes();
		} catch (error) {
			console.error("Error deleting note:", error);
		} finally {
			setIsDeletingNote(false);
			setShowDeleteNoteDialog(false);
			setNoteToDelete(null);
		}
	}, [noteToDelete, refetchNotes]);

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
				onAddSearchSpace={handleAddSearchSpace}
				searchSpace={activeSearchSpace}
				navItems={navItems}
				onNavItemClick={handleNavItemClick}
				chats={chats}
				activeChatId={currentChatId}
				onNewChat={handleNewChat}
				onChatSelect={handleChatSelect}
				onChatDelete={handleChatDelete}
				onViewAllChats={handleViewAllChats}
				notes={notes}
				activeNoteId={currentNoteId}
				onNoteSelect={handleNoteSelect}
				onNoteDelete={handleNoteDelete}
				onAddNote={handleAddNote}
				onViewAllNotes={handleViewAllNotes}
				user={{ email: user?.email || "", name: user?.email?.split("@")[0] }}
				onSettings={handleSettings}
				onManageMembers={handleManageMembers}
				onSeeAllSearchSpaces={handleSeeAllSearchSpaces}
				onUserSettings={handleUserSettings}
				onLogout={handleLogout}
				pageUsage={pageUsage}
				breadcrumb={breadcrumb}
				languageSwitcher={languageSwitcher}
				theme={theme}
				onToggleTheme={handleToggleTheme}
				isChatPage={isChatPage}
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

			{/* All Chats Sidebar */}
			<AllChatsSidebar
				open={isAllChatsSidebarOpen}
				onOpenChange={setIsAllChatsSidebarOpen}
				searchSpaceId={searchSpaceId}
			/>

			{/* All Notes Sidebar */}
			<AllNotesSidebar
				open={isAllNotesSidebarOpen}
				onOpenChange={setIsAllNotesSidebarOpen}
				searchSpaceId={searchSpaceId}
				onAddNote={handleAddNote}
			/>

			{/* All Search Spaces Sheet */}
			<AllSearchSpacesSheet
				open={isAllSearchSpacesSheetOpen}
				onOpenChange={setIsAllSearchSpacesSheetOpen}
				searchSpaces={searchSpaces}
				onSearchSpaceSelect={handleSearchSpaceSelect}
				onCreateNew={() => {
					setIsAllSearchSpacesSheetOpen(false);
					setIsCreateSearchSpaceDialogOpen(true);
				}}
				onSettings={handleSearchSpaceSettings}
				onDelete={handleDeleteSearchSpace}
			/>

			{/* Create Search Space Dialog */}
			<CreateSearchSpaceDialog
				open={isCreateSearchSpaceDialogOpen}
				onOpenChange={setIsCreateSearchSpaceDialogOpen}
			/>

			{/* Delete Note Dialog */}
			<Dialog open={showDeleteNoteDialog} onOpenChange={setShowDeleteNoteDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>{t("delete_note")}</span>
						</DialogTitle>
						<DialogDescription>
							{t("delete_note_confirm")} <span className="font-medium">{noteToDelete?.name}</span>?{" "}
							{t("action_cannot_undone")}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowDeleteNoteDialog(false)}
							disabled={isDeletingNote}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							onClick={confirmDeleteNote}
							disabled={isDeletingNote}
							className="gap-2"
						>
							{isDeletingNote ? (
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
		</>
	);
}
