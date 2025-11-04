"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

interface Chat {
	created_at: string;
	id: number;
	type: string;
	title: string;
	messages: string[];
	search_space_id: number;
}

interface UseChatsOptions {
	searchSpaceId: string | number;
	limit?: number;
	skip?: number;
	autoFetch?: boolean;
}

export function useChats({
	searchSpaceId,
	limit = 5,
	skip = 0,
	autoFetch = true,
}: UseChatsOptions) {
	const [chats, setChats] = useState<Chat[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchChats = useCallback(async () => {
		try {
			// Only run on client-side
			if (typeof window === "undefined") return;

			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats?limit=${limit}&skip=${skip}&search_space_id=${searchSpaceId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (response.status === 401) {
				// Clear token and redirect to home
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized: Redirecting to login page");
			}

			if (!response.ok) {
				throw new Error(`Failed to fetch chats: ${response.status}`);
			}

			const data = await response.json();

			// Sort chats by created_at in descending order (newest first)
			const sortedChats = data.sort(
				(a: Chat, b: Chat) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
			);

			setChats(sortedChats);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch chats");
			console.error("Error fetching chats:", err);
			setChats([]);
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId, limit, skip]);

	const deleteChat = useCallback(async (chatId: number) => {
		try {
			// Only run on client-side
			if (typeof window === "undefined") return;

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${chatId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "DELETE",
				}
			);

			if (response.status === 401) {
				// Clear token and redirect to home
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized: Redirecting to login page");
			}

			if (!response.ok) {
				throw new Error(`Failed to delete chat: ${response.status}`);
			}

			// Update local state to remove the deleted chat
			setChats((prev) => prev.filter((chat) => chat.id !== chatId));
		} catch (err: any) {
			console.error("Error deleting chat:", err);
			throw err;
		}
	}, []);

	useEffect(() => {
		if (autoFetch) {
			fetchChats();

			// Set up a refresh interval (every 5 minutes)
			const intervalId = setInterval(fetchChats, 5 * 60 * 1000);

			// Clean up interval on component unmount
			return () => clearInterval(intervalId);
		}
	}, [autoFetch, fetchChats]);

	return { chats, loading, error, fetchChats, deleteChat };
}
