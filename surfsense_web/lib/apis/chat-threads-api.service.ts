import {
	type PublicChatSnapshotCreateRequest,
	type PublicChatSnapshotCreateResponse,
	type PublicChatSnapshotDeleteRequest,
	type PublicChatSnapshotListRequest,
	type PublicChatSnapshotListResponse,
	type PublicChatSnapshotsBySpaceRequest,
	type PublicChatSnapshotsBySpaceResponse,
	publicChatSnapshotCreateRequest,
	publicChatSnapshotCreateResponse,
	publicChatSnapshotDeleteRequest,
	publicChatSnapshotListRequest,
	publicChatSnapshotListResponse,
	publicChatSnapshotsBySpaceRequest,
	publicChatSnapshotsBySpaceResponse,
} from "@/contracts/types/chat-threads.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ChatThreadsApiService {
	/**
	 * Create a public chat snapshot for a thread.
	 */
	createPublicChatSnapshot = async (
		request: PublicChatSnapshotCreateRequest
	): Promise<PublicChatSnapshotCreateResponse> => {
		const parsed = publicChatSnapshotCreateRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/threads/${parsed.data.thread_id}/snapshots`,
			publicChatSnapshotCreateResponse
		);
	};

	/**
	 * List all public chat snapshots for a thread.
	 */
	listPublicChatSnapshots = async (
		request: PublicChatSnapshotListRequest
	): Promise<PublicChatSnapshotListResponse> => {
		const parsed = publicChatSnapshotListRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/threads/${parsed.data.thread_id}/snapshots`,
			publicChatSnapshotListResponse
		);
	};

	/**
	 * Delete a public chat snapshot.
	 */
	deletePublicChatSnapshot = async (request: PublicChatSnapshotDeleteRequest): Promise<void> => {
		const parsed = publicChatSnapshotDeleteRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		await baseApiService.delete(
			`/api/v1/threads/${parsed.data.thread_id}/snapshots/${parsed.data.snapshot_id}`
		);
	};

	/**
	 * List all public chat snapshots for a search space.
	 */
	listPublicChatSnapshotsForSearchSpace = async (
		request: PublicChatSnapshotsBySpaceRequest
	): Promise<PublicChatSnapshotsBySpaceResponse> => {
		const parsed = publicChatSnapshotsBySpaceRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/searchspaces/${parsed.data.search_space_id}/snapshots`,
			publicChatSnapshotsBySpaceResponse
		);
	};
}

export const chatThreadsApiService = new ChatThreadsApiService();
