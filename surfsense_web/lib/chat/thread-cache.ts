import type { QueryClient, QueryKey } from "@tanstack/react-query";
import type {
	ThreadListItem,
	ThreadListResponse,
	ThreadRecord,
} from "@/lib/chat/thread-persistence";

type WorkspaceKey = number | string;

type ThreadMetadataPatch = Partial<ThreadRecord> &
	Partial<ThreadListItem> & {
		has_comments?: boolean;
	};

function isSameWorkspace(keyValue: unknown, workspaceId: WorkspaceKey): boolean {
	return String(keyValue) === String(workspaceId);
}

function isThreadListResponse(value: unknown): value is ThreadListResponse {
	return (
		typeof value === "object" &&
		value !== null &&
		Array.isArray((value as ThreadListResponse).threads) &&
		Array.isArray((value as ThreadListResponse).archived_threads)
	);
}

function isThreadListItemArray(value: unknown): value is ThreadListItem[] {
	return Array.isArray(value);
}

function listItemPatchFromMetadata(patch: ThreadMetadataPatch): Partial<ThreadListItem> {
	const listPatch: Partial<ThreadListItem> = {};

	if (patch.title !== undefined) listPatch.title = patch.title;
	if (patch.archived !== undefined) listPatch.archived = patch.archived;
	if (patch.visibility !== undefined) listPatch.visibility = patch.visibility;
	if (patch.created_by_id !== undefined) listPatch.created_by_id = patch.created_by_id;
	if (patch.created_at !== undefined) listPatch.createdAt = patch.created_at;
	if (patch.updated_at !== undefined) listPatch.updatedAt = patch.updated_at;
	if (patch.createdAt !== undefined) listPatch.createdAt = patch.createdAt;
	if (patch.updatedAt !== undefined) listPatch.updatedAt = patch.updatedAt;

	return listPatch;
}

function patchListItem(
	item: ThreadListItem,
	threadId: number,
	patch: ThreadMetadataPatch
): ThreadListItem {
	if (item.id !== threadId) return item;
	return {
		...item,
		...listItemPatchFromMetadata(patch),
	};
}

function patchThreadListResponse(
	response: ThreadListResponse,
	threadId: number,
	patch: ThreadMetadataPatch
): ThreadListResponse {
	return {
		...response,
		threads: response.threads.map((item) => patchListItem(item, threadId, patch)),
		archived_threads: response.archived_threads.map((item) => patchListItem(item, threadId, patch)),
	};
}

function patchThreadListItems(
	items: ThreadListItem[],
	threadId: number,
	patch: ThreadMetadataPatch
): ThreadListItem[] {
	return items.map((item) => patchListItem(item, threadId, patch));
}

function patchThreadRecord(
	record: ThreadRecord,
	threadId: number,
	patch: ThreadMetadataPatch
): ThreadRecord {
	if (record.id !== threadId) return record;
	return {
		...record,
		...patch,
	};
}

function threadListQueryFilter(workspaceId: WorkspaceKey) {
	return {
		predicate: ({ queryKey }: { queryKey: QueryKey }) =>
			Array.isArray(queryKey) &&
			queryKey[0] === "threads" &&
			isSameWorkspace(queryKey[1], workspaceId),
	};
}

function allThreadsQueryFilter(workspaceId: WorkspaceKey) {
	return {
		predicate: ({ queryKey }: { queryKey: QueryKey }) =>
			Array.isArray(queryKey) &&
			queryKey[0] === "all-threads" &&
			isSameWorkspace(queryKey[1], workspaceId),
	};
}

function searchThreadsQueryFilter(workspaceId: WorkspaceKey) {
	return {
		predicate: ({ queryKey }: { queryKey: QueryKey }) =>
			Array.isArray(queryKey) &&
			queryKey[0] === "search-threads" &&
			isSameWorkspace(queryKey[1], workspaceId),
	};
}

function threadDetailQueryFilter(threadId: number) {
	return {
		predicate: ({ queryKey }: { queryKey: QueryKey }) =>
			Array.isArray(queryKey) &&
			queryKey[0] === "threads" &&
			queryKey[1] === "detail" &&
			Number(queryKey[2]) === threadId,
	};
}

function threadMessagesQueryFilter(threadId: number) {
	return {
		predicate: ({ queryKey }: { queryKey: QueryKey }) =>
			Array.isArray(queryKey) &&
			queryKey[0] === "threads" &&
			queryKey[1] === "messages" &&
			Number(queryKey[2]) === threadId,
	};
}

function updateThreadListResponse(
	queryClient: QueryClient,
	filter: ReturnType<typeof threadListQueryFilter>,
	threadId: number,
	patch: ThreadMetadataPatch
): void {
	queryClient.setQueriesData<ThreadListResponse>(filter, (old) => {
		if (!isThreadListResponse(old)) return old;
		return patchThreadListResponse(old, threadId, patch);
	});
}

export function patchThreadEverywhere(
	queryClient: QueryClient,
	workspaceId: WorkspaceKey,
	threadId: number,
	patch: ThreadMetadataPatch
): void {
	updateThreadListResponse(queryClient, threadListQueryFilter(workspaceId), threadId, patch);
	updateThreadListResponse(queryClient, allThreadsQueryFilter(workspaceId), threadId, patch);

	queryClient.setQueriesData<ThreadListItem[]>(searchThreadsQueryFilter(workspaceId), (old) => {
		if (!isThreadListItemArray(old)) return old;
		return patchThreadListItems(old, threadId, patch);
	});

	queryClient.setQueriesData<ThreadRecord>(threadDetailQueryFilter(threadId), (old) => {
		if (!old) return old;
		return patchThreadRecord(old, threadId, patch);
	});
}

export function replaceThreadEverywhere(
	queryClient: QueryClient,
	workspaceId: WorkspaceKey,
	thread: ThreadRecord
): void {
	patchThreadEverywhere(queryClient, workspaceId, thread.id, thread);
}

export function removeThreadEverywhere(
	queryClient: QueryClient,
	workspaceId: WorkspaceKey,
	threadId: number
): void {
	const removeFromListResponse = (old: ThreadListResponse | undefined) => {
		if (!isThreadListResponse(old)) return old;
		return {
			...old,
			threads: old.threads.filter((thread) => thread.id !== threadId),
			archived_threads: old.archived_threads.filter((thread) => thread.id !== threadId),
		};
	};

	queryClient.setQueriesData<ThreadListResponse>(
		threadListQueryFilter(workspaceId),
		removeFromListResponse
	);
	queryClient.setQueriesData<ThreadListResponse>(
		allThreadsQueryFilter(workspaceId),
		removeFromListResponse
	);
	queryClient.setQueriesData<ThreadListItem[]>(searchThreadsQueryFilter(workspaceId), (old) => {
		if (!isThreadListItemArray(old)) return old;
		return old.filter((thread) => thread.id !== threadId);
	});
	queryClient.removeQueries(threadDetailQueryFilter(threadId));
	queryClient.removeQueries(threadMessagesQueryFilter(threadId));
}

export function moveThreadArchiveState(
	queryClient: QueryClient,
	workspaceId: WorkspaceKey,
	threadId: number,
	archived: boolean
): void {
	const moveInListResponse = (old: ThreadListResponse | undefined) => {
		if (!isThreadListResponse(old)) return old;

		const activeWithoutThread = old.threads.filter((thread) => thread.id !== threadId);
		const archivedWithoutThread = old.archived_threads.filter((thread) => thread.id !== threadId);
		const existing =
			old.threads.find((thread) => thread.id === threadId) ??
			old.archived_threads.find((thread) => thread.id === threadId);

		if (!existing) return old;

		const updated = { ...existing, archived };

		return {
			...old,
			threads: archived ? activeWithoutThread : [updated, ...activeWithoutThread],
			archived_threads: archived ? [updated, ...archivedWithoutThread] : archivedWithoutThread,
		};
	};

	queryClient.setQueriesData<ThreadListResponse>(
		threadListQueryFilter(workspaceId),
		moveInListResponse
	);
	queryClient.setQueriesData<ThreadListResponse>(
		allThreadsQueryFilter(workspaceId),
		moveInListResponse
	);
	queryClient.setQueriesData<ThreadListItem[]>(searchThreadsQueryFilter(workspaceId), (old) => {
		if (!isThreadListItemArray(old)) return old;
		return old.map((thread) => (thread.id === threadId ? { ...thread, archived } : thread));
	});
	queryClient.setQueriesData<ThreadRecord>(threadDetailQueryFilter(threadId), (old) => {
		if (!old || old.id !== threadId) return old;
		return { ...old, archived };
	});
}
