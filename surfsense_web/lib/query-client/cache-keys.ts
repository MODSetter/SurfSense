import type { GetChatsRequest } from "@/contracts/types/chat.types";

export const cacheKeys = {
	chats: {
		activeChat: (chatId: string) => ["active-chat", chatId] as const,
		globalQueryParams: (queries: GetChatsRequest["queryParams"]) =>
			["chats", ...(queries ? Object.values(queries) : [])] as const,
	},
	podcasts: () => ["podcasts"] as const,
	auth: {
		user: ["auth", "user"] as const,
	},
};
