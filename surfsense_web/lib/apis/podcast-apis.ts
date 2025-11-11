import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";
import type { GeneratePodcastRequest } from "@/components/chat/ChatPanel/ChatPanelContainer";

export const getPodcastByChatId = async (chatId: string, authToken: string) => {
	try {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/by-chat/${Number(chatId)}`,
			{
				headers: {
					Authorization: `Bearer ${authToken}`,
				},
				method: "GET",
			}
		);

		if (!response.ok) {
			const errorData = await response.json().catch(() => ({}));
			throw new Error(errorData.detail || "Failed to fetch podcast");
		}

		return (await response.json()) as PodcastItem | null;
	} catch (err: any) {
		console.error("Error fetching podcast:", err);

		return null;
	}
};

export const generatePodcast = async (request: GeneratePodcastRequest, authToken: string) => {
	try {
		const { podcast_title = "SurfSense Podcast" } = request;

		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/generate/`,
			{
				method: "POST",
				headers: {
					Authorization: `Bearer ${authToken}`,
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ ...request, podcast_title }),
			}
		);

		if (!response.ok) {
			const errorData = await response.json().catch(() => ({}));
			throw new Error(errorData.detail || "Failed to generate podcast");
		}
	} catch (error) {
		console.error("Error generating podcast:", error);
	}
};
