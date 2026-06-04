"use client";

import { type QueryClient, useQuery } from "@tanstack/react-query";
import {
	getThreadFull,
	getThreadMessages,
	type ThreadHistoryLoadResponse,
	type ThreadRecord,
} from "@/lib/chat/thread-persistence";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const THREAD_DETAIL_STALE_TIME_MS = 60 * 1000;
const THREAD_MESSAGES_STALE_TIME_MS = 30 * 1000;

function isValidThreadId(threadId: number | null | undefined): threadId is number {
	return typeof threadId === "number" && threadId > 0;
}

export function useThreadDetail(threadId: number | null | undefined) {
	return useQuery<ThreadRecord>({
		queryKey: cacheKeys.threads.detail(threadId ?? 0),
		queryFn: () => getThreadFull(threadId as number),
		enabled: isValidThreadId(threadId),
		staleTime: THREAD_DETAIL_STALE_TIME_MS,
	});
}

export function useThreadMessages(threadId: number | null | undefined) {
	return useQuery<ThreadHistoryLoadResponse>({
		queryKey: cacheKeys.threads.messages(threadId ?? 0),
		queryFn: () => getThreadMessages(threadId as number),
		enabled: isValidThreadId(threadId),
		staleTime: THREAD_MESSAGES_STALE_TIME_MS,
	});
}

export function prefetchThreadData(queryClient: QueryClient, threadId: number): void {
	if (!isValidThreadId(threadId)) return;

	void Promise.all([
		queryClient.prefetchQuery({
			queryKey: cacheKeys.threads.detail(threadId),
			queryFn: () => getThreadFull(threadId),
			staleTime: THREAD_DETAIL_STALE_TIME_MS,
		}),
		queryClient.prefetchQuery({
			queryKey: cacheKeys.threads.messages(threadId),
			queryFn: () => getThreadMessages(threadId),
			staleTime: THREAD_MESSAGES_STALE_TIME_MS,
		}),
	]);
}
