import {
	type CreateCommentRequest,
	type CreateReplyRequest,
	createCommentRequest,
	createCommentResponse,
	createReplyRequest,
	createReplyResponse,
	type DeleteCommentRequest,
	deleteCommentRequest,
	deleteCommentResponse,
	type GetCommentsRequest,
	type GetMentionsRequest,
	getCommentsRequest,
	getCommentsResponse,
	getMentionsRequest,
	getMentionsResponse,
	type UpdateCommentRequest,
	updateCommentRequest,
	updateCommentResponse,
} from "@/contracts/types/chat-comments.types";
import { ValidationError } from "@/lib/error";
import { baseApiService } from "./base-api.service";

class ChatCommentsApiService {
	/**
	 * Get comments for a message
	 */
	getComments = async (request: GetCommentsRequest) => {
		const parsed = getCommentsRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/messages/${parsed.data.message_id}/comments`,
			getCommentsResponse
		);
	};

	/**
	 * Create a top-level comment
	 */
	createComment = async (request: CreateCommentRequest) => {
		const parsed = createCommentRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/messages/${parsed.data.message_id}/comments`,
			createCommentResponse,
			{ body: { content: parsed.data.content } }
		);
	};

	/**
	 * Create a reply to a comment
	 */
	createReply = async (request: CreateReplyRequest) => {
		const parsed = createReplyRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/comments/${parsed.data.comment_id}/replies`,
			createReplyResponse,
			{ body: { content: parsed.data.content } }
		);
	};

	/**
	 * Update a comment
	 */
	updateComment = async (request: UpdateCommentRequest) => {
		const parsed = updateCommentRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(`/api/v1/comments/${parsed.data.comment_id}`, updateCommentResponse, {
			body: { content: parsed.data.content },
		});
	};

	/**
	 * Delete a comment
	 */
	deleteComment = async (request: DeleteCommentRequest) => {
		const parsed = deleteCommentRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/comments/${parsed.data.comment_id}`,
			deleteCommentResponse
		);
	};

	/**
	 * Get mentions for current user
	 */
	getMentions = async (request?: GetMentionsRequest) => {
		const parsed = getMentionsRequest.safeParse(request ?? {});

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const params = new URLSearchParams();
		if (parsed.data.search_space_id !== undefined) {
			params.set("search_space_id", String(parsed.data.search_space_id));
		}

		const queryString = params.toString();
		const url = queryString ? `/api/v1/mentions?${queryString}` : "/api/v1/mentions";

		return baseApiService.get(url, getMentionsResponse);
	};
}

export const chatCommentsApiService = new ChatCommentsApiService();
