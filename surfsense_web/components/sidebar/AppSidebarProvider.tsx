"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";
import { hasUnsavedEditorChangesAtom, pendingEditorNavigationAtom } from "@/atoms/editor/ui.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { notesApiService } from "@/lib/apis/notes-api.service";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { deleteThread, fetchThreads } from "@/lib/chat/thread-persistence";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface AppSidebarProviderProps {
	searchSpaceId: string;
	navSecondary: {
		title: string;
		url: string;
		icon: string;
	}[];
	navMain: {
		title: string;
		url: string;
		icon: string;
		isActive?: boolean;
		items?: {
			title: string;
			url: string;
		}[];
	}[];
}

export function AppSidebarProvider({
	searchSpaceId,
	navSecondary,
	navMain,
}: AppSidebarProviderProps) {
	const t = useTranslations("dashboard");
	const tCommon = useTranslations("common");
	const router = useRouter();
	const queryClient = useQueryClient();
	const [isDeletingThread, setIsDeletingThread] = useState(false);

	// Editor state for handling unsaved changes
	const hasUnsavedEditorChanges = useAtomValue(hasUnsavedEditorChangesAtom);
	const setPendingNavigation = useSetAtom(pendingEditorNavigationAtom);

	// Fetch new chat threads
	const {
		data: threadsData,
		error: threadError,
		isLoading: isLoadingThreads,
		refetch: refetchThreads,
	} = useQuery({
		queryKey: ["threads", searchSpaceId],
		queryFn: () => fetchThreads(Number(searchSpaceId), 4),
		enabled: !!searchSpaceId,
	});

	const {
		data: searchSpace,
		isLoading: isLoadingSearchSpace,
		error: searchSpaceError,
		refetch: fetchSearchSpace,
	} = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: Number(searchSpaceId) }),
		enabled: !!searchSpaceId,
	});

	const { data: user } = useAtomValue(currentUserAtom);

	// Fetch notes
	const {
		data: notesData,
		error: notesError,
		isLoading: isLoadingNotes,
		refetch: refetchNotes,
	} = useQuery({
		queryKey: ["notes", searchSpaceId],
		queryFn: () =>
			notesApiService.getNotes({
				search_space_id: Number(searchSpaceId),
				page_size: 4, // Get 4 notes for compact sidebar
			}),
		enabled: !!searchSpaceId,
	});

	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [threadToDelete, setThreadToDelete] = useState<{ id: number; name: string } | null>(null);
	const [showDeleteNoteDialog, setShowDeleteNoteDialog] = useState(false);
	const [noteToDelete, setNoteToDelete] = useState<{
		id: number;
		name: string;
		search_space_id: number;
	} | null>(null);
	const [isDeletingNote, setIsDeletingNote] = useState(false);

	// Retry function
	const retryFetch = useCallback(() => {
		fetchSearchSpace();
	}, [fetchSearchSpace]);

	// Transform threads to the format expected by AppSidebar
	const recentChats = useMemo(() => {
		if (!threadsData?.threads) return [];

		// Threads are already sorted by updated_at desc from the API
		return threadsData.threads.map((thread) => ({
			name: thread.title || `Chat ${thread.id}`,
			url: `/dashboard/${searchSpaceId}/new-chat/${thread.id}`,
			icon: "MessageCircleMore",
			id: thread.id,
			search_space_id: Number(searchSpaceId),
			actions: [
				{
					name: "Delete",
					icon: "Trash2",
					onClick: () => {
						setThreadToDelete({
							id: thread.id,
							name: thread.title || `Chat ${thread.id}`,
						});
						setShowDeleteDialog(true);
					},
				},
			],
		}));
	}, [threadsData, searchSpaceId]);

	// Handle delete thread
	const handleDeleteThread = useCallback(async () => {
		if (!threadToDelete) return;

		setIsDeletingThread(true);
		try {
			await deleteThread(threadToDelete.id, searchSpaceId);
			// Invalidate threads query to refresh the list
			queryClient.invalidateQueries({ queryKey: ["threads", searchSpaceId] });
		} catch (error) {
			console.error("Error deleting thread:", error);
		} finally {
			setIsDeletingThread(false);
			setShowDeleteDialog(false);
			setThreadToDelete(null);
		}
	}, [threadToDelete, queryClient, searchSpaceId]);

	// Handle delete note with confirmation
	const handleDeleteNote = useCallback(async () => {
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

	// Memoized fallback chats
	const fallbackChats = useMemo(() => {
		if (threadError) {
			return [
				{
					name: t("error_loading_chats"),
					url: "#",
					icon: "AlertCircle",
					id: 0,
					search_space_id: Number(searchSpaceId),
					actions: [
						{
							name: tCommon("retry"),
							icon: "RefreshCw",
							onClick: () => refetchThreads(),
						},
					],
				},
			];
		}

		return [];
	}, [threadError, searchSpaceId, refetchThreads, t, tCommon]);

	// Use fallback chats if there's an error or no chats
	const displayChats = recentChats.length > 0 ? recentChats : fallbackChats;

	// Transform notes to the format expected by NavNotes
	const recentNotes = useMemo(() => {
		if (!notesData?.items) return [];

		// Sort notes by updated_at (most recent first), fallback to created_at if updated_at is null
		const sortedNotes = [...notesData.items].sort((a, b) => {
			const dateA = a.updated_at
				? new Date(a.updated_at).getTime()
				: new Date(a.created_at).getTime();
			const dateB = b.updated_at
				? new Date(b.updated_at).getTime()
				: new Date(b.created_at).getTime();
			return dateB - dateA; // Descending order (most recent first)
		});

		// Limit to 4 notes for compact sidebar
		return sortedNotes.slice(0, 4).map((note) => ({
			name: note.title,
			url: `/dashboard/${note.search_space_id}/editor/${note.id}`,
			icon: "FileText",
			id: note.id,
			search_space_id: note.search_space_id,
			actions: [
				{
					name: "Delete",
					icon: "Trash2",
					onClick: () => {
						setNoteToDelete({
							id: note.id,
							name: note.title,
							search_space_id: note.search_space_id,
						});
						setShowDeleteNoteDialog(true);
					},
				},
			],
		}));
	}, [notesData]);

	// Handle add note - check for unsaved changes first
	const handleAddNote = useCallback(() => {
		const newNoteUrl = `/dashboard/${searchSpaceId}/editor/new`;

		if (hasUnsavedEditorChanges) {
			// Set pending navigation - the editor will show the unsaved changes dialog
			setPendingNavigation(newNoteUrl);
		} else {
			// No unsaved changes, navigate directly
			router.push(newNoteUrl);
		}
	}, [router, searchSpaceId, hasUnsavedEditorChanges, setPendingNavigation]);

	// Memoized updated navSecondary
	const updatedNavSecondary = useMemo(() => {
		const updated = [...navSecondary];
		if (updated.length > 0) {
			updated[0] = {
				...updated[0],
				title:
					searchSpace?.name ||
					(isLoadingSearchSpace
						? tCommon("loading")
						: searchSpaceError
							? t("error_loading_space")
							: t("unknown_search_space")),
			};
		}
		return updated;
	}, [navSecondary, searchSpace?.name, isLoadingSearchSpace, searchSpaceError, t, tCommon]);

	// Prepare page usage data
	const pageUsage = user
		? {
				pagesUsed: user.pages_used,
				pagesLimit: user.pages_limit,
			}
		: undefined;

	return (
		<>
			<AppSidebar
				searchSpaceId={searchSpaceId}
				navSecondary={updatedNavSecondary}
				navMain={navMain}
				RecentChats={displayChats}
				RecentNotes={recentNotes}
				onAddNote={handleAddNote}
				pageUsage={pageUsage}
			/>

			{/* Delete Confirmation Dialog */}
			<Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>{t("delete_chat")}</span>
						</DialogTitle>
						<DialogDescription>
							{t("delete_chat_confirm")} <span className="font-medium">{threadToDelete?.name}</span>
							? {t("action_cannot_undone")}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowDeleteDialog(false)}
							disabled={isDeletingThread}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							onClick={handleDeleteThread}
							disabled={isDeletingThread}
							className="gap-2"
						>
							{isDeletingThread ? (
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

			{/* Delete Note Confirmation Dialog */}
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
							onClick={handleDeleteNote}
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
