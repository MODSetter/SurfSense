export const cacheKeys = {
	activeChat: (chatId: string) => ["activeChat", chatId],
	activeSearchSpaceChats: (searchSpaceId: string) => ["activeSearchSpaceChats", searchSpaceId],
};
