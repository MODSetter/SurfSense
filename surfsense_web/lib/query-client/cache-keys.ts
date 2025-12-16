import type { GetChatsRequest } from "@/contracts/types/chat.types";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";
import type { GetLLMConfigsRequest } from "@/contracts/types/llm-config.types";
import type { GetPodcastsRequest } from "@/contracts/types/podcast.types";
import type { GetSearchSpacesRequest } from "@/contracts/types/search-space.types";

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
		withQueryParams: (queries: GetDocumentsRequest["queryParams"]) =>
			["documents-with-queries", ...(queries ? Object.values(queries) : [])] as const,
		document: (documentId: string) => ["document", documentId] as const,
		typeCounts: (searchSpaceId?: string) => ["documents", "type-counts", searchSpaceId] as const,
		byChunk: (chunkId: string) => ["documents", "by-chunk", chunkId] as const,
	},
	llmConfigs: {
		global: () => ["llm-configs", "global"] as const,
		all: (searchSpaceId: string) => ["llm-configs", searchSpaceId] as const,
		withQueryParams: (queries: GetLLMConfigsRequest["queryParams"]) =>
			["llm-configs", ...(queries ? Object.values(queries) : [])] as const,
		byId: (llmConfigId: string) => ["llm-config", llmConfigId] as const,
		preferences: (searchSpaceId: string) => ["llm-preferences", searchSpaceId] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
	searchSpaces: {
		all: ["search-spaces"] as const,
		withQueryParams: (queries: GetSearchSpacesRequest["queryParams"]) =>
			["search-spaces", ...(queries ? Object.values(queries) : [])] as const,
		detail: (searchSpaceId: string) => ["search-spaces", searchSpaceId] as const,
		communityPrompts: ["search-spaces", "community-prompts"] as const,
	}
};
