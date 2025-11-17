import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";
import type { GeneratePodcastRequest } from "@/components/chat/ChatPanel/ChatPanelContainer";

export const getPodcastByChatId = async (chatId: string, authToken: string) => {
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
};

export const generatePodcast = async (request: GeneratePodcastRequest, authToken: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/generate/`,
		{
			method: "POST",
			headers: {
				Authorization: `Bearer ${authToken}`,
				"Content-Type": "application/json",
			},
			body: JSON.stringify(request),
		}
	);

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}));
		throw new Error(errorData.detail || "Failed to generate podcast");
	}

	return await response.json();
};

export const loadPodcast = async (podcast: PodcastItem, authToken: string) => {
	const controller = new AbortController();
	const timeoutId = setTimeout(() => controller.abort(), 30000);

	try {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcast.id}/stream`,
			{
				headers: {
					Authorization: `Bearer ${authToken}`,
				},
				signal: controller.signal,
			}
		);

		if (!response.ok) {
			throw new Error(`Failed to fetch audio stream: ${response.statusText}`);
		}

		const blob = await response.blob();
		const objectUrl = URL.createObjectURL(blob);
		return objectUrl;
	} catch (error) {
		if (error instanceof DOMException && error.name === "AbortError") {
			throw new Error("Request timed out. Please try again.");
		}
		throw error;
	} finally {
		clearTimeout(timeoutId);
	}
};
