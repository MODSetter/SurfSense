/**
 * Thread persistence utilities for the new chat feature.
 * Provides API functions and thread list management.
 */

import { baseApiService } from "@/lib/apis/base-api.service";

// =============================================================================
// Types matching backend schemas
// =============================================================================

export interface ThreadRecord {
	id: number;
	title: string;
	archived: boolean;
	search_space_id: number;
	created_at: string;
	updated_at: string;
}

export interface MessageRecord {
	id: number;
	thread_id: number;
	role: "user" | "assistant" | "system";
	content: unknown;
	created_at: string;
}

export interface ThreadListResponse {
	threads: ThreadListItem[];
	archived_threads: ThreadListItem[];
}

export interface ThreadListItem {
	id: number;
	title: string;
	archived: boolean;
	createdAt: string;
	updatedAt: string;
}

export interface ThreadHistoryLoadResponse {
	messages: MessageRecord[];
}

// =============================================================================
// API Service Functions
// =============================================================================

/**
 * Fetch list of threads for a search space
 */
export async function fetchThreads(
	searchSpaceId: number
): Promise<ThreadListResponse> {
	return baseApiService.get<ThreadListResponse>(
		`/api/v1/threads?search_space_id=${searchSpaceId}`
	);
}

/**
 * Create a new thread
 */
export async function createThread(
	searchSpaceId: number,
	title = "New Chat"
): Promise<ThreadRecord> {
	return baseApiService.post<ThreadRecord>("/api/v1/threads", undefined, {
		body: {
			title,
			archived: false,
			search_space_id: searchSpaceId,
		},
	});
}

/**
 * Get thread messages
 */
export async function getThreadMessages(
	threadId: number
): Promise<ThreadHistoryLoadResponse> {
	return baseApiService.get<ThreadHistoryLoadResponse>(
		`/api/v1/threads/${threadId}`
	);
}

/**
 * Append a message to a thread
 */
export async function appendMessage(
	threadId: number,
	message: { role: "user" | "assistant" | "system"; content: unknown }
): Promise<MessageRecord> {
	return baseApiService.post<MessageRecord>(
		`/api/v1/threads/${threadId}/messages`,
		undefined,
		{ body: message }
	);
}

/**
 * Update thread (rename, archive)
 */
export async function updateThread(
	threadId: number,
	updates: { title?: string; archived?: boolean }
): Promise<ThreadRecord> {
	return baseApiService.put<ThreadRecord>(
		`/api/v1/threads/${threadId}`,
		undefined,
		{ body: updates }
	);
}

/**
 * Delete a thread
 */
export async function deleteThread(threadId: number): Promise<void> {
	await baseApiService.delete(`/api/v1/threads/${threadId}`);
}

// =============================================================================
// Thread List Manager (for thread list sidebar)
// =============================================================================

export interface ThreadListAdapterConfig {
	searchSpaceId: number;
	currentThreadId: number | null;
	onThreadSwitch: (threadId: number) => void;
	onNewThread: (threadId: number) => void;
}

export interface ThreadListState {
	threads: ThreadListItem[];
	archivedThreads: ThreadListItem[];
	isLoading: boolean;
	error: string | null;
}

/**
 * Creates a thread list management object.
 * This provides methods to manage the thread list for the sidebar.
 */
export function createThreadListManager(config: ThreadListAdapterConfig) {
	return {
		async loadThreads(): Promise<ThreadListState> {
			try {
				const response = await fetchThreads(config.searchSpaceId);
				return {
					threads: response.threads,
					archivedThreads: response.archived_threads,
					isLoading: false,
					error: null,
				};
			} catch (error) {
				console.error("[ThreadListManager] Failed to load threads:", error);
				return {
					threads: [],
					archivedThreads: [],
					isLoading: false,
					error:
						error instanceof Error ? error.message : "Failed to load threads",
				};
			}
		},

		async createNewThread(title = "New Chat"): Promise<number | null> {
			try {
				const thread = await createThread(config.searchSpaceId, title);
				config.onNewThread(thread.id);
				return thread.id;
			} catch (error) {
				console.error("[ThreadListManager] Failed to create thread:", error);
				return null;
			}
		},

		switchToThread(threadId: number) {
			config.onThreadSwitch(threadId);
		},

		async renameThread(threadId: number, newTitle: string): Promise<boolean> {
			try {
				await updateThread(threadId, { title: newTitle });
				return true;
			} catch (error) {
				console.error("[ThreadListManager] Failed to rename thread:", error);
				return false;
			}
		},

		async archiveThread(threadId: number): Promise<boolean> {
			try {
				await updateThread(threadId, { archived: true });
				return true;
			} catch (error) {
				console.error("[ThreadListManager] Failed to archive thread:", error);
				return false;
			}
		},

		async unarchiveThread(threadId: number): Promise<boolean> {
			try {
				await updateThread(threadId, { archived: false });
				return true;
			} catch (error) {
				console.error("[ThreadListManager] Failed to unarchive thread:", error);
				return false;
			}
		},

		async deleteThread(threadId: number): Promise<boolean> {
			try {
				await deleteThread(threadId);
				return true;
			} catch (error) {
				console.error("[ThreadListManager] Failed to delete thread:", error);
				return false;
			}
		},
	};
}
