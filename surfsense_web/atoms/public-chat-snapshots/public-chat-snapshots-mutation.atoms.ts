import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type { PublicChatSnapshotDeleteRequest } from "@/contracts/types/chat-threads.types";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";

export const deletePublicChatSnapshotMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: PublicChatSnapshotDeleteRequest) => {
		return chatThreadsApiService.deletePublicChatSnapshot(request);
	},
	onSuccess: () => {
		toast.success("Public link deleted");
	},
	onError: (error: Error) => {
		console.error("Failed to delete public chat link:", error);
		toast.error("Failed to delete public link");
	},
}));
