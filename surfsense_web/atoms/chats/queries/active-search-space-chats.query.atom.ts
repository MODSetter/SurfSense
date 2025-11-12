import { atomWithQuery } from "jotai-tanstack-query";
import { fetchChatsBySearchSpace } from "@/lib/apis/chat-apis";
import { activeSearchSpaceIdAtom } from "../../seach-spaces/active-seach-space.atom";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const activeSearchSpaceChatsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = localStorage.getItem("surfsense_bearer_token");

	return {
		queryKey: cacheKeys.activeSearchSpace.chats(searchSpaceId ?? ""),
		enabled: !!searchSpaceId && !!authToken,
		queryFn: async () => {
			if (!authToken) {
				throw new Error("No authentication token found");
			}
			if (!searchSpaceId) {
				throw new Error("No search space id found");
			}

			return fetchChatsBySearchSpace(searchSpaceId, authToken);
		},
	};
});
