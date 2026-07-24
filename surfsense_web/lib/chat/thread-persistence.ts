/**
 * Thread persistence utilities for the new chat feature.
 * Provides API functions and thread list management.
 */

import { baseApiService } from "@/lib/apis/base-api.service";
import { buildBackendUrl } from "@/lib/env-config";
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
	workspace_id: number;
	created_at: string;
	updated_at: string;
	has_comments?: boolean;
}

export interface TokenUsageSummary {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	/**
	 * Total provider USD cost for this assistant turn, in micro-USD
	 * (1_000_000 = $1.00). Optional because rows persisted before the
	 * cost-credits migration won't have it.
	 */
	cost_micros?: number;
	model_breakdown?: Record<
		string,
		{
			prompt_tokens: number;
			completion_tokens: number;
			total_tokens: number;
			cost_micros?: number;
		}
	> | null;
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
	token_usage?: TokenUsageSummary | null;
	// Per-turn correlation id from ``configurable.turn_id`` at streaming
	// time (added in migration 136). Used by the per-turn revert
	// endpoint and edit-from-arbitrary-position. Nullable on legacy
	// rows that predate the column.
	turn_id?: string | null;
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
 * Fetch list of threads for a workspace
 */
export async function fetchThreads(
	workspaceId: number,
	limit?: number
): Promise<ThreadListResponse> {
	const params = new URLSearchParams({ workspace_id: String(workspaceId) });
	if (limit) params.append("limit", String(limit));
	return baseApiService.get<ThreadListResponse>(`/api/v1/threads?${params}`);
}

/**
 * Search threads by title
 */
export async function searchThreads(workspaceId: number, title: string): Promise<ThreadListItem[]> {
	const params = new URLSearchParams({
		workspace_id: String(workspaceId),
		title,
	});
	return baseApiService.get<ThreadListItem[]>(`/api/v1/threads/search?${params}`);
}

/**
 * Create a new thread
 */
export async function createThread(workspaceId: number, title = "New Chat"): Promise<ThreadRecord> {
	return baseApiService.post<ThreadRecord>("/api/v1/threads", undefined, {
		body: {
			title,
			archived: false,
			workspace_id: workspaceId,
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
 * Append a message to a thread.
 *
 * ``turn_id`` is the per-turn correlation id streamed by the backend
 * via ``data-turn-info``. Persisting it lets later edits locate the
 * matching LangGraph checkpoint without HumanMessage scanning. Older
 * callers can still omit it for back-compat.
 *
 * @deprecated Replaced by the SSE-based message ID handshake. The
 * streaming generator (`stream_new_chat` / `stream_resume_chat`) now
 * persists both the user and assistant rows server-side via
 * `persist_user_turn` / `persist_assistant_shell` and emits
 * `data-user-message-id` / `data-assistant-message-id` SSE events so
 * the UI renames its optimistic IDs in real time. The only remaining
 * caller is `persistAssistantErrorMessage` (pre-stream error fallback
 * for requests the server never accepted — the server has nothing to
 * persist in that case). After the legacy route is removed in a
 * follow-up PR this function will be deleted entirely.
 */
export async function appendMessage(
	threadId: number,
	message: {
		role: "user" | "assistant" | "system";
		content: unknown;
		token_usage?: unknown;
		turn_id?: string | null;
	}
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
	workspaceId: number;
	userQuery?: string | null; // New user query (for edit). Null/undefined = reload with same query
	attachments?: Array<{
		id: string;
		name: string;
		type: string;
		content: string;
	}>;
	mentionedDocumentIds?: number[];
}

/**
 * Get the URL for the regenerate endpoint (for streaming fetch)
 */
export function getRegenerateUrl(threadId: number): string {
	return buildBackendUrl(`/api/v1/threads/${threadId}/regenerate`);
}
