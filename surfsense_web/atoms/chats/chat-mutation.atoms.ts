import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	ChatSummary,
	CreateChatRequest,
	DeleteChatRequest,
	UpdateChatRequest,
} from "@/contracts/types/chat.types";
import { chatsApiService } from "@/lib/apis/chats-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";
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
			// Optimistically update the current query
			queryClient.setQueryData(
				cacheKeys.chats.globalQueryParams(chatsQueryParams),
				(oldData: ChatSummary[]) => {
					return oldData?.filter((chat) => chat.id !== request.id) ?? [];
				}
			);
			// Invalidate all chat queries to ensure consistency across components
			queryClient.invalidateQueries({
				queryKey: ["chats"],
			});
			// Also invalidate the "all-chats" query used by AllChatsSidebar
			queryClient.invalidateQueries({
				queryKey: ["all-chats"],
			});
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
			// Invalidate ALL chat queries to ensure sidebar and other components refresh
			// Using a partial key match to avoid stale closure issues with specific query params
			queryClient.invalidateQueries({
				queryKey: ["chats"],
			});
			// Also invalidate the "all-chats" query used by AllChatsSidebar
			queryClient.invalidateQueries({
				queryKey: ["all-chats"],
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
