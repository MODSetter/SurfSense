import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { chatCommentsApiService } from "@/lib/apis/chat-comments-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const mentionsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.mentions.all(searchSpaceId ? Number(searchSpaceId) : undefined),
		staleTime: 60 * 1000, // 1 minute
		queryFn: async () => {
			return chatCommentsApiService.getMentions({
				search_space_id: searchSpaceId ? Number(searchSpaceId) : undefined,
			});
		},
	};
});

export const unreadMentionsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.mentions.unreadOnly(searchSpaceId ? Number(searchSpaceId) : undefined),
		staleTime: 30 * 1000, // 30 seconds
		queryFn: async () => {
			return chatCommentsApiService.getMentions({
				search_space_id: searchSpaceId ? Number(searchSpaceId) : undefined,
				unread_only: true,
			});
		},
	};
});

