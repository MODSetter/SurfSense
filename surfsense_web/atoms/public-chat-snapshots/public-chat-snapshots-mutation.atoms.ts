import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	PublicChatSnapshotCreateRequest,
	PublicChatSnapshotCreateResponse,
	PublicChatSnapshotDeleteRequest,
} from "@/contracts/types/chat-threads.types";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createPublicChatSnapshotMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: PublicChatSnapshotCreateRequest) => {
		return chatThreadsApiService.createPublicChatSnapshot(request);
	},
	onSuccess: (response: PublicChatSnapshotCreateResponse) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.publicChatSnapshots.all,
		});

		const publicUrl = `${window.location.origin}/public/${response.share_token}`;
		navigator.clipboard.writeText(publicUrl);
		if (response.is_new) {
			toast.success("Public link created and copied to clipboard", {
				description: "Anyone with this link can view a snapshot of this chat",
			});
		} else {
			toast.success("Public link copied to clipboard", {
				description: "This snapshot already exists",
			});
		}
	},
	onError: (error: Error) => {
		console.error("Failed to create snapshot:", error);
		toast.error("Failed to create public link");
	},
}));

export const deletePublicChatSnapshotMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: PublicChatSnapshotDeleteRequest) => {
		return chatThreadsApiService.deletePublicChatSnapshot(request);
	},
	onSuccess: () => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.publicChatSnapshots.all,
		});
		toast.success("Public link deleted");
	},
	onError: (error: Error) => {
		console.error("Failed to delete public chat link:", error);
		toast.error("Failed to delete public link");
	},
}));
