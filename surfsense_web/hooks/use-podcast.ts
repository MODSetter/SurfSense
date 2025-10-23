import { useCallback } from "react";
import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";

export function usePodcast() {
	const getPodcastByChatId = useCallback(async (chatId: number) => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/by-chat/${chatId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch podcast");
			}

			return (await response.json()) as PodcastItem;
		} catch (err: any) {
			console.error("Error fetching podcast:", err);
			throw err;
		}
	}, []);

	return { getPodcastByChatId };
}
