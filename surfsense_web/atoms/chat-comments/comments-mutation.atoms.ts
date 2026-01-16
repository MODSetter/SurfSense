import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateCommentRequest,
	CreateReplyRequest,
	DeleteCommentRequest,
	UpdateCommentRequest,
} from "@/contracts/types/chat-comments.types";
import { chatCommentsApiService } from "@/lib/apis/chat-comments-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createCommentMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: CreateCommentRequest) => {
		return chatCommentsApiService.createComment(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.comments.byMessage(variables.message_id),
		});
	},
	onError: (error: Error) => {
		console.error("Error creating comment:", error);
		toast.error("Failed to create comment");
	},
}));

export const createReplyMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: CreateReplyRequest & { message_id: number }) => {
		return chatCommentsApiService.createReply(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.comments.byMessage(variables.message_id),
		});
	},
	onError: (error: Error) => {
		console.error("Error creating reply:", error);
		toast.error("Failed to create reply");
	},
}));

export const updateCommentMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: UpdateCommentRequest & { message_id: number }) => {
		return chatCommentsApiService.updateComment(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.comments.byMessage(variables.message_id),
		});
	},
	onError: (error: Error) => {
		console.error("Error updating comment:", error);
		toast.error("Failed to update comment");
	},
}));

export const deleteCommentMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: DeleteCommentRequest & { message_id: number }) => {
		return chatCommentsApiService.deleteComment(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.comments.byMessage(variables.message_id),
		});
		toast.success("Comment deleted");
	},
	onError: (error: Error) => {
		console.error("Error deleting comment:", error);
		toast.error("Failed to delete comment");
	},
}));
