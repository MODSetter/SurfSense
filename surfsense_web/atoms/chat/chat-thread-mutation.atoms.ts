import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	TogglePublicShareRequest,
	TogglePublicShareResponse,
} from "@/contracts/types/chat-threads.types";
import { chatThreadsApiService } from "@/lib/apis/chat-threads-api.service";

export const togglePublicShareMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: TogglePublicShareRequest) => {
		return chatThreadsApiService.togglePublicShare(request);
	},
	onSuccess: (response: TogglePublicShareResponse) => {
		if (response.enabled && response.share_token) {
			const publicUrl = `${window.location.origin}/public/${response.share_token}`;
			navigator.clipboard.writeText(publicUrl);
			toast.success("Public link copied to clipboard", {
				description: "Anyone with this link can view the chat",
			});
		} else {
			toast.success("Public sharing disabled");
		}
	},
	onError: (error: Error) => {
		console.error("Failed to toggle public share:", error);
		toast.error("Failed to update public sharing");
	},
}));
