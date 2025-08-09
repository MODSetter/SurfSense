"use client";

import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import { apiClient } from "@/lib/api";

interface Chat {
	created_at: string;
	id: number;
	type: string;
	title: string;
	messages: string[];
	search_space_id: number;
}

interface SearchSpace {
	created_at: string;
	id: number;
	name: string;
	description: string;
	user_id: string;
}

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
	const [recentChats, setRecentChats] = useState<
		{
			name: string;
			url: string;
			icon: string;
			id: number;
			search_space_id: number;
			actions: { name: string; icon: string; onClick: () => void }[];
		}[]
	>([]);
	const [searchSpace, setSearchSpace] = useState<SearchSpace | null>(null);
	const [isLoadingChats, setIsLoadingChats] = useState(true);
	const [isLoadingSearchSpace, setIsLoadingSearchSpace] = useState(true);
	const [chatError, setChatError] = useState<string | null>(null);
	const [searchSpaceError, setSearchSpaceError] = useState<string | null>(null);
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; name: string } | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [isClient, setIsClient] = useState(false);

	// Set isClient to true when component mounts on the client
	useEffect(() => {
		setIsClient(true);
	}, []);

	// Memoized fetch function for chats
	const fetchRecentChats = useCallback(async () => {
		try {
			// Only run on client-side
			if (typeof window === "undefined") return;

			const chats: Chat[] = await apiClient.get<Chat[]>(
				`api/v1/chats/?limit=5&skip=0&search_space_id=${searchSpaceId}`
			);

			// Sort chats by created_at in descending order (newest first)
			const sortedChats = chats.sort(
				(a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
			);

			// Transform API response to the format expected by AppSidebar
			const formattedChats = sortedChats.map((chat) => ({
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
			}));

			setRecentChats(formattedChats);
			setChatError(null);
		} catch (error) {
			console.error("Error fetching chats:", error);
			setChatError(error instanceof Error ? error.message : "Unknown error occurred");
			setRecentChats([]);
		} finally {
			setIsLoadingChats(false);
		}
	}, [searchSpaceId]);

	// Memoized fetch function for search space
	const fetchSearchSpace = useCallback(async () => {
		try {
			// Only run on client-side
			if (typeof window === "undefined") return;

			const data: SearchSpace = await apiClient.get<SearchSpace>(
				`api/v1/searchspaces/${searchSpaceId}`
			);
			setSearchSpace(data);
			setSearchSpaceError(null);
		} catch (error) {
			console.error("Error fetching search space:", error);
			setSearchSpaceError(error instanceof Error ? error.message : "Unknown error occurred");
		} finally {
			setIsLoadingSearchSpace(false);
		}
	}, [searchSpaceId]);

	// Retry function
	const retryFetch = useCallback(() => {
		setChatError(null);
		setSearchSpaceError(null);
		setIsLoadingChats(true);
		setIsLoadingSearchSpace(true);
		fetchRecentChats();
		fetchSearchSpace();
	}, [fetchRecentChats, fetchSearchSpace]);

	// Fetch recent chats
	useEffect(() => {
		fetchRecentChats();

		// Set up a refresh interval (every 5 minutes)
		const intervalId = setInterval(fetchRecentChats, 5 * 60 * 1000);

		// Clean up interval on component unmount
		return () => clearInterval(intervalId);
	}, [fetchRecentChats]);

	// Fetch search space details
	useEffect(() => {
		fetchSearchSpace();
	}, [fetchSearchSpace]);

	// Handle delete chat with better error handling
	const handleDeleteChat = useCallback(async () => {
		if (!chatToDelete) return;

		try {
			setIsDeleting(true);

			await apiClient.delete(`api/v1/chats/${chatToDelete.id}`);

			// Update local state
			setRecentChats((prev) => prev.filter((chat) => chat.id !== chatToDelete.id));
		} catch (error) {
			console.error("Error deleting chat:", error);
			// You could show a toast notification here
		} finally {
			setIsDeleting(false);
			setShowDeleteDialog(false);
			setChatToDelete(null);
		}
	}, [chatToDelete]);

	// Memoized fallback chats
	const fallbackChats = useMemo(() => {
		if (chatError) {
			return [
				{
					name: "Error loading chats",
					url: "#",
					icon: "AlertCircle",
					id: 0,
					search_space_id: Number(searchSpaceId),
					actions: [
						{
							name: "Retry",
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
					name: "No recent chats",
					url: "#",
					icon: "MessageCircleMore",
					id: 0,
					search_space_id: Number(searchSpaceId),
					actions: [],
				},
			];
		}

		return [];
	}, [chatError, isLoadingChats, recentChats.length, searchSpaceId, retryFetch]);

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
						? "Loading..."
						: searchSpaceError
							? "Error loading search space"
							: "Unknown Search Space"),
			};
		}
		return updated;
	}, [navSecondary, isClient, searchSpace?.name, isLoadingSearchSpace, searchSpaceError]);

	// Show loading state if not client-side
	if (!isClient) {
		return <AppSidebar navSecondary={navSecondary} navMain={navMain} RecentChats={[]} />;
	}

	return (
		<>
			<AppSidebar navSecondary={updatedNavSecondary} navMain={navMain} RecentChats={displayChats} />

			{/* Delete Confirmation Dialog */}
			<Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>Delete Chat</span>
						</DialogTitle>
						<DialogDescription>
							Are you sure you want to delete{" "}
							<span className="font-medium">{chatToDelete?.name}</span>? This action cannot be
							undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setShowDeleteDialog(false)}
							disabled={isDeleting}
						>
							Cancel
						</Button>
						<Button
							variant="destructive"
							onClick={handleDeleteChat}
							disabled={isDeleting}
							className="gap-2"
						>
							{isDeleting ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									Deleting...
								</>
							) : (
								<>
									<Trash2 className="h-4 w-4" />
									Delete
								</>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</>
	);
}
