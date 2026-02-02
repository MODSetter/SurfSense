import {
	type CreateSnapshotRequest,
	type CreateSnapshotResponse,
	createSnapshotRequest,
	createSnapshotResponse,
	type DeleteSnapshotRequest,
	deleteSnapshotRequest,
	type ListSearchSpaceSnapshotsRequest,
	type ListSearchSpaceSnapshotsResponse,
	type ListSnapshotsRequest,
	type ListSnapshotsResponse,
	listSearchSpaceSnapshotsRequest,
	listSearchSpaceSnapshotsResponse,
	listSnapshotsRequest,
	listSnapshotsResponse,
} from "@/contracts/types/chat-threads.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class ChatThreadsApiService {
	/**
	 * Create a public snapshot for a thread.
	 */
	createSnapshot = async (request: CreateSnapshotRequest): Promise<CreateSnapshotResponse> => {
		const parsed = createSnapshotRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/threads/${parsed.data.thread_id}/snapshots`,
			createSnapshotResponse
		);
	};

	/**
	 * List all snapshots for a thread.
	 */
	listSnapshots = async (request: ListSnapshotsRequest): Promise<ListSnapshotsResponse> => {
		const parsed = listSnapshotsRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/threads/${parsed.data.thread_id}/snapshots`,
			listSnapshotsResponse
		);
	};

	/**
	 * Delete a specific snapshot.
	 */
	deleteSnapshot = async (request: DeleteSnapshotRequest): Promise<void> => {
		const parsed = deleteSnapshotRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		await baseApiService.delete(
			`/api/v1/threads/${parsed.data.thread_id}/snapshots/${parsed.data.snapshot_id}`
		);
	};

	/**
	 * List all snapshots for a search space.
	 */
	listSearchSpaceSnapshots = async (
		request: ListSearchSpaceSnapshotsRequest
	): Promise<ListSearchSpaceSnapshotsResponse> => {
		const parsed = listSearchSpaceSnapshotsRequest.safeParse(request);

		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/searchspaces/${parsed.data.search_space_id}/snapshots`,
			listSearchSpaceSnapshotsResponse
		);
	};
}

export const chatThreadsApiService = new ChatThreadsApiService();
