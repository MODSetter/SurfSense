import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	PublicChatSnapshotCreateRequest,
	PublicChatSnapshotCreateResponse,
} from "@/contracts/types/chat-threads.types";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";

export const createPublicChatSnapshotMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: PublicChatSnapshotCreateRequest) => {
		return chatThreadsApiService.createPublicChatSnapshot(request);
	},
	onSuccess: (response: PublicChatSnapshotCreateResponse) => {
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
