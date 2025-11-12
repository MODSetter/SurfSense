import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import type { ChatDetails } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";
import { fetchChatDetails } from "@/lib/apis/chat-apis";
import { getPodcastByChatId } from "@/lib/apis/podcast-apis";

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
		queryKey: ["activeChat", activeChatId],
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
				fetchChatDetails(activeChatId, authToken),
			]);

			return { chatId: activeChatId, chatDetails, podcast };
		},
	};
});
