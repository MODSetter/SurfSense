import { atomWithMutation } from "jotai-tanstack-query";
import { deleteChat } from "@/lib/apis/chat-apis";
import { activeSearchSpaceIdAtom } from "../../seach-spaces/active-seach-space.atom";
import { queryClient } from "@/lib/query-client/client";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { toast } from "sonner";

export const deleteChatMutationAtom = atomWithMutation((get) => {
  const searchSpaceId = get(activeSearchSpaceIdAtom);
  const authToken = localStorage.getItem("surfsense_bearer_token");

  return {
    mutationKey: cacheKeys.activeSearchSpace.chats(searchSpaceId ?? ""),
    enabled: !!searchSpaceId && !!authToken,
    mutationFn: async (chatId: number) => {
      if (!authToken) {
        throw new Error("No authentication token found");
      }
      if (!searchSpaceId) {
        throw new Error("No search space id found");
      }

      return deleteChat(chatId, authToken);
    },

    onSuccess: () => {
      toast.success("Chat deleted successfully");
      queryClient.invalidateQueries({
        queryKey: cacheKeys.activeSearchSpace.chats(searchSpaceId!),
      });
    },
  };
});
