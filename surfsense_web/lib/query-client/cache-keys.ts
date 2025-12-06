import type { GetChatsRequest } from "@/contracts/types/chat.types";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";
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
	documents: {
		globalQueryParams: (queries: GetDocumentsRequest["queryParams"]) =>
			["documents", ...(queries ? Object.values(queries) : [])] as const,
		document: (documentId: string) => ["document", documentId] as const,
		typeCounts: (searchSpaceId?: string) => ["documents", "type-counts", searchSpaceId] as const,
		byChunk: (chunkId: string) => ["documents", "by-chunk", chunkId] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
};
