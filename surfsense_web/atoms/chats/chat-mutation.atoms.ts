import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type { Chat } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import type {
	CreateChatRequest,
	DeleteChatRequest,
	UpdateChatRequest,
} from "@/contracts/types/chat.types";
import { chatsApiService } from "@/lib/apis/chats-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-queries.atom";
import { globalChatsQueryParamsAtom } from "./ui.atoms";

export const deleteChatMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = getBearerToken();
	const chatsQueryParams = get(globalChatsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.chats.globalQueryParams(chatsQueryParams),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: DeleteChatRequest) => {
			return chatsApiService.deleteChat(request);
		},

		onSuccess: (_, request: DeleteChatRequest) => {
			toast.success("Chat deleted successfully");
			queryClient.setQueryData(
				cacheKeys.chats.globalQueryParams(chatsQueryParams),
				(oldData: Chat[]) => {
					return oldData.filter((chat) => chat.id !== request.id);
				}
			);
		},
	};
});

export const createChatMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = getBearerToken();
	const chatsQueryParams = get(globalChatsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.chats.globalQueryParams(chatsQueryParams),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: CreateChatRequest) => {
			return chatsApiService.createChat(request);
		},

		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: cacheKeys.chats.globalQueryParams(chatsQueryParams),
			});
		},
	};
});

export const updateChatMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = getBearerToken();
	const chatsQueryParams = get(globalChatsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.chats.globalQueryParams(chatsQueryParams),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: UpdateChatRequest) => {
			return chatsApiService.updateChat(request);
		},

		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: cacheKeys.chats.globalQueryParams(chatsQueryParams),
			});
		},
	};
});
