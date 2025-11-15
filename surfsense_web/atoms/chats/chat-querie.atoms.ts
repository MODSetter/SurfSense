import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import type { ChatDetails } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import { fetchChatDetails, fetchChatsBySearchSpace } from "@/lib/apis/chats.api";
import { chatApiService } from "@/lib/apis/chats-api.service";
import { getPodcastByChatId } from "@/lib/apis/podcasts.api";
import { cacheKeys } from "@/lib/query-client/cache-keys";

type ActiveChatState = {
	chatId: string | null;
	chatDetails: ChatDetails | null;
	podcast: PodcastItem | null;
};

export const activeChatIdAtom = atom<string | null>(null);

export const activeChatAtom = atomWithQuery<ActiveChatState>((get) => {
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
				getPodcastByChatId(activeChatId, authToken),
				chatApiService.getChatDetails({ id: Number(activeChatId) }),
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
			return chatApiService.getChatsBySearchSpace({ search_space_id: Number(searchSpaceId) });
		},
	};
});
