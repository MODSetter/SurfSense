import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type { Chat } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import { chatApiService } from "@/lib/apis/chats-api.service";
import { AUTH_TOKEN_KEY } from "@/lib/constants";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../seach-spaces/seach-space-queries.atom";

export const deleteChatMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = localStorage.getItem(AUTH_TOKEN_KEY);

	return {
		mutationKey: cacheKeys.activeSearchSpace.chats(searchSpaceId ?? ""),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (chatId: number) => {
			return chatApiService.deleteChat({ id: chatId });
		},

		onSuccess: (_, chatId) => {
			toast.success("Chat deleted successfully");
			queryClient.setQueryData(
				cacheKeys.activeSearchSpace.chats(searchSpaceId!),
				(oldData: Chat[]) => {
					return oldData.filter((chat) => chat.id !== chatId);
				}
			);
		},
	};
});
