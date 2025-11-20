import type { GetChatsRequest } from "@/contracts/types/chat.types";
import type { GetPodcastsRequest } from "@/contracts/types/podcast.types";

export const cacheKeys = {
	chats: {
		activeChat: (chatId: string) => ["active-chat", chatId] as const,
		globalQueryParams: (queries: GetChatsRequest["queryParams"]) =>
			["chats", ...(queries ? Object.values(queries) : [])] as const,
	},
	podcasts: {
		globalQueryParams: (queries: GetPodcastsRequest["queryParams"]) =>
			["podcasts", ...(queries ? Object.values(queries) : [])] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
};
