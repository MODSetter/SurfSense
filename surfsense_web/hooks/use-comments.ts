import { useQuery } from "@tanstack/react-query";
import { chatCommentsApiService } from "@/lib/apis/chat-comments-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface UseCommentsOptions {
	messageId: number;
	enabled?: boolean;
}

export function useComments({ messageId, enabled = true }: UseCommentsOptions) {
	return useQuery({
		queryKey: cacheKeys.comments.byMessage(messageId),
		queryFn: async () => {
			return chatCommentsApiService.getComments({ message_id: messageId });
		},
		enabled: enabled && !!messageId,
	});
}
