/**
 * Thread persistence utilities for the new chat feature.
 * Provides API functions and thread list management.
 */

import { baseApiService } from "@/lib/apis/base-api.service";

// =============================================================================
// Types matching backend schemas
// =============================================================================

/**
 * Chat visibility levels - matches backend ChatVisibility enum
 */
export type ChatVisibility = "PRIVATE" | "SEARCH_SPACE";

export interface ThreadRecord {
	id: number;
	title: string;
	archived: boolean;
	visibility: ChatVisibility;
	created_by_id: string | null;
	search_space_id: number;
	created_at: string;
	updated_at: string;
	has_comments?: boolean;
}

export interface MessageRecord {
	id: number;
	thread_id: number;
	role: "user" | "assistant" | "system";
	content: unknown;
	created_at: string;
	author_id?: string | null;
	author_display_name?: string | null;
	author_avatar_url?: string | null;
}

export interface ThreadListResponse {
	threads: ThreadListItem[];
	archived_threads: ThreadListItem[];
}

export interface ThreadListItem {
	id: number;
	title: string;
	archived: boolean;
	visibility: ChatVisibility;
	created_by_id: string | null;
	is_own_thread: boolean;
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
	searchSpaceId: number,
	limit?: number
): Promise<ThreadListResponse> {
	const params = new URLSearchParams({ search_space_id: String(searchSpaceId) });
	if (limit) params.append("limit", String(limit));
	return baseApiService.get<ThreadListResponse>(`/api/v1/threads?${params}`);
}

/**
 * Search threads by title
 */
export async function searchThreads(
	searchSpaceId: number,
	title: string
): Promise<ThreadListItem[]> {
	const params = new URLSearchParams({
		search_space_id: String(searchSpaceId),
		title,
	});
	return baseApiService.get<ThreadListItem[]>(`/api/v1/threads/search?${params}`);
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
export async function getThreadMessages(threadId: number): Promise<ThreadHistoryLoadResponse> {
	return baseApiService.get<ThreadHistoryLoadResponse>(`/api/v1/threads/${threadId}`);
}

/**
 * Append a message to a thread
 */
export async function appendMessage(
	threadId: number,
	message: { role: "user" | "assistant" | "system"; content: unknown }
): Promise<MessageRecord> {
	return baseApiService.post<MessageRecord>(`/api/v1/threads/${threadId}/messages`, undefined, {
		body: message,
	});
}

/**
 * Update thread (rename, archive)
 */
export async function updateThread(
	threadId: number,
	updates: { title?: string; archived?: boolean }
): Promise<ThreadRecord> {
	return baseApiService.put<ThreadRecord>(`/api/v1/threads/${threadId}`, undefined, {
		body: updates,
	});
}

/**
 * Delete a thread
 */
export async function deleteThread(threadId: number): Promise<void> {
	await baseApiService.delete(`/api/v1/threads/${threadId}`);
}

/**
 * Update thread visibility (share/unshare)
 */
export async function updateThreadVisibility(
	threadId: number,
	visibility: ChatVisibility
): Promise<ThreadRecord> {
	return baseApiService.patch<ThreadRecord>(`/api/v1/threads/${threadId}/visibility`, undefined, {
		body: { visibility },
	});
}

/**
 * Get full thread details including visibility
 */
export async function getThreadFull(threadId: number): Promise<ThreadRecord> {
	return baseApiService.get<ThreadRecord>(`/api/v1/threads/${threadId}/full`);
}

/**
 * Regeneration request parameters
 */
export interface RegenerateParams {
	searchSpaceId: number;
	userQuery?: string | null; // New user query (for edit). Null/undefined = reload with same query
	attachments?: Array<{
		id: string;
		name: string;
		type: string;
		content: string;
	}>;
	mentionedDocumentIds?: number[];
	mentionedSurfsenseDocIds?: number[];
}

/**
 * Get the URL for the regenerate endpoint (for streaming fetch)
 */
export function getRegenerateUrl(threadId: number): string {
	const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
	return `${backendUrl}/api/v1/threads/${threadId}/regenerate`;
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
					error: error instanceof Error ? error.message : "Failed to load threads",
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
