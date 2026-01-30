import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateSnapshotRequest,
	CreateSnapshotResponse,
} from "@/contracts/types/chat-threads.types";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";

export const createSnapshotMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: CreateSnapshotRequest) => {
		return chatThreadsApiService.createSnapshot(request);
	},
	onSuccess: (response: CreateSnapshotResponse) => {
		// Construct URL using frontend origin (backend returns its own URL which differs)
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
