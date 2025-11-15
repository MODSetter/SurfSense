export const cacheKeys = {
	activeSearchSpace: {
		chats: (searchSpaceId: string) => ["active-search-space", "chats", searchSpaceId] as const,
		activeChat: (chatId: string) => ["active-search-space", "active-chat", chatId] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
};
