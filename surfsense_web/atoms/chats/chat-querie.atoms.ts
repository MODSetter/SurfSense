import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import { chatsApiService } from "@/lib/apis/chats-api.service";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeChatIdAtom } from "./ui.atoms";

export const activeChatAtom = atomWithQuery((get) => {
	const activeChatId = get(activeChatIdAtom);
	const authToken = localStorage.getItem("surfsense_bearer_token");

	return {
		queryKey: cacheKeys.activeSearchSpace.activeChat(activeChatId ?? ""),
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

export const activeSearchSpaceChatsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = localStorage.getItem("surfsense_bearer_token");

	return {
		queryKey: cacheKeys.activeSearchSpace.chats(searchSpaceId ?? ""),
		enabled: !!searchSpaceId && !!authToken,
		queryFn: async () => {
			return chatsApiService.getChatsBySearchSpace({
				queryParams: { search_space_id: searchSpaceId! },
			});
		},
	};
});
