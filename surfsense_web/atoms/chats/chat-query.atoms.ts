import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { chatsApiService } from "@/lib/apis/chats-api.service";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeChatIdAtom, globalChatsQueryParamsAtom } from "./ui.atoms";

export const activeChatAtom = atomWithQuery((get) => {
	const activeChatId = get(activeChatIdAtom);
	const authToken = getBearerToken();

	return {
		queryKey: cacheKeys.chats.activeChat(activeChatId ?? ""),
		enabled: !!activeChatId && !!authToken,
		queryFn: async () => {
			if (!authToken) {
				throw new Error("No authentication token found");
			}
			if (!activeChatId) {
				throw new Error("No active chat id found");
			}

			const [podcast, chatDetails] = await Promise.all([
				podcastsApiService.getPodcastByChatId({ chat_id: Number(activeChatId) }),
				chatsApiService.getChatDetails({ id: Number(activeChatId) }),
			]);

			return { chatId: activeChatId, chatDetails, podcast };
		},
	};
});

export const chatsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = getBearerToken();
	const queryParams = get(globalChatsQueryParamsAtom);

	return {
		queryKey: cacheKeys.chats.globalQueryParams(queryParams),
		enabled: !!searchSpaceId && !!authToken,
		queryFn: async () => {
			return chatsApiService.getChats({
				queryParams: queryParams,
			});
		},
	};
});
