import { useQuery } from "@tanstack/react-query";
import type { GetPublicChatResponse } from "@/contracts/types/public-chat.types";
import { publicChatApiService } from "@/lib/apis/public-chat-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export function usePublicChat(shareToken: string) {
	return useQuery<GetPublicChatResponse, Error>({
		queryKey: cacheKeys.publicChat.byToken(shareToken),
		queryFn: () => publicChatApiService.getPublicChat({ share_token: shareToken }),
		enabled: !!shareToken,
		staleTime: 30_000,
		retry: false,
	});
}
