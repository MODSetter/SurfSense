"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { deleteChatMutationAtom } from "@/atoms/chats/chat-mutation.atoms";
import { chatsAtom } from "@/atoms/chats/chat-query.atoms";
import { globalChatsQueryParamsAtom } from "@/atoms/chats/ui.atoms";
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
import { useSearchSpace, useUser } from "@/hooks";

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
	const setChatsQueryParams = useSetAtom(globalChatsQueryParamsAtom);
	const { data: chats, error: chatError, isLoading: isLoadingChats } = useAtomValue(chatsAtom);
	const [{ isPending: isDeletingChat, mutateAsync: deleteChat, error: deleteError }] =
		useAtom(deleteChatMutationAtom);

	useEffect(() => {
		setChatsQueryParams((prev) => ({ ...prev, search_space_id: searchSpaceId, skip: 0, limit: 5 }));
	}, [searchSpaceId]);

	const {
		searchSpace,
		loading: isLoadingSearchSpace,
		error: searchSpaceError,
		fetchSearchSpace,
	} = useSearchSpace({ searchSpaceId });

	const { user } = useUser();

	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; name: string } | null>(null);
	const [isClient, setIsClient] = useState(false);

	// Set isClient to true when component mounts on the client
	useEffect(() => {
		setIsClient(true);
	}, []);

	// Retry function
	const retryFetch = useCallback(() => {
		fetchSearchSpace();
	}, [fetchSearchSpace]);

	// Transform API response to the format expected by AppSidebar
	const recentChats = useMemo(() => {
		return chats
			? chats.map((chat) => ({
					name: chat.title || `Chat ${chat.id}`,
					url: `/dashboard/${chat.search_space_id}/researcher/${chat.id}`,
					icon: "MessageCircleMore",
					id: chat.id,
					search_space_id: chat.search_space_id,
					actions: [
						{
							name: "Delete",
							icon: "Trash2",
							onClick: () => {
								setChatToDelete({ id: chat.id, name: chat.title || `Chat ${chat.id}` });
								setShowDeleteDialog(true);
							},
						},
					],
				}))
			: [];
	}, [chats]);

	// Handle delete chat with better error handling
	const handleDeleteChat = useCallback(async () => {
		if (!chatToDelete) return;

		try {
			await deleteChat({ id: chatToDelete.id });
		} catch (error) {
			console.error("Error deleting chat:", error);
			// You could show a toast notification here
		} finally {
			setShowDeleteDialog(false);
			setChatToDelete(null);
		}
	}, [chatToDelete, deleteChat]);

	// Memoized fallback chats
	const fallbackChats = useMemo(() => {
		if (chatError) {
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
							onClick: retryFetch,
						},
					],
				},
			];
		}

		if (!isLoadingChats && recentChats.length === 0) {
			return [
				{
					name: t("no_recent_chats"),
					url: "#",
					icon: "MessageCircleMore",
					id: 0,
					search_space_id: Number(searchSpaceId),
					actions: [],
				},
			];
		}

		return [];
	}, [chatError, isLoadingChats, recentChats.length, searchSpaceId, retryFetch, t, tCommon]);

	// Use fallback chats if there's an error or no chats
	const displayChats = recentChats.length > 0 ? recentChats : fallbackChats;

	// Memoized updated navSecondary
	const updatedNavSecondary = useMemo(() => {
		const updated = [...navSecondary];
		if (updated.length > 0 && isClient) {
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
	}, [
		navSecondary,
		isClient,
		searchSpace?.name,
		isLoadingSearchSpace,
		searchSpaceError,
		t,
		tCommon,
	]);

	// Prepare page usage data
	const pageUsage = user
		? {
				pagesUsed: user.pages_used,
				pagesLimit: user.pages_limit,
			}
		: undefined;

	// Show loading state if not client-side
	if (!isClient) {
		return (
			<AppSidebar
				searchSpaceId={searchSpaceId}
				navSecondary={navSecondary}
				navMain={navMain}
				RecentChats={[]}
				pageUsage={pageUsage}
			/>
		);
	}

	return (
		<>
			<AppSidebar
				searchSpaceId={searchSpaceId}
				navSecondary={updatedNavSecondary}
				navMain={navMain}
				RecentChats={displayChats}
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
							{t("delete_chat_confirm")} <span className="font-medium">{chatToDelete?.name}</span>?{" "}
							{t("action_cannot_undone")}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowDeleteDialog(false)}
							disabled={isDeletingChat}
						>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							onClick={handleDeleteChat}
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
		</>
	);
}
