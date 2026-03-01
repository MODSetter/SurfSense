import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import type { GetCommentsResponse } from "@/contracts/types/chat-comments.types";
import { chatCommentsApiService } from "@/lib/apis/chat-comments-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface UseCommentsOptions {
	messageId: number;
	enabled?: boolean;
}

// ---------------------------------------------------------------------------
// Module-level coordination: when a batch request is in-flight, individual
// useComments queryFns piggy-back on it instead of making their own requests.
//
// _batchReady is a promise that resolves once the batch useEffect has had a
// chance to set _batchInflight. Individual queryFns await this gate before
// deciding whether to piggy-back or fetch on their own, eliminating the
// previous race where setTimeout(0) was not enough.
// ---------------------------------------------------------------------------
let _batchInflight: Promise<void> | null = null;
let _batchTargetIds = new Set<number>();
let _batchReady: Promise<void> | null = null;
let _resolveBatchReady: (() => void) | null = null;

function resetBatchGate(resolveImmediately = false) {
	_batchReady = new Promise<void>((r) => {
		_resolveBatchReady = r;
		if (resolveImmediately) r();
	});
}

// Open the initial gate immediately (no batch pending yet)
resetBatchGate(true);

export function useComments({ messageId, enabled = true }: UseCommentsOptions) {
	const queryClient = useQueryClient();

	return useQuery<GetCommentsResponse>({
		queryKey: cacheKeys.comments.byMessage(messageId),
		queryFn: async () => {
			// Wait for the batch gate so the useEffect in useBatchCommentsPreload
			// has a chance to set _batchInflight before we decide.
			if (_batchReady) {
				await _batchReady;
			}

			if (_batchInflight && _batchTargetIds.has(messageId)) {
				await _batchInflight;
				const cached = queryClient.getQueryData<GetCommentsResponse>(cacheKeys.comments.byMessage(messageId));
				if (cached) return cached;
			}

			return chatCommentsApiService.getComments({ message_id: messageId });
		},
		enabled: enabled && !!messageId,
		staleTime: 30_000,
	});
}

/**
 * Batch-fetch comments for all given message IDs in a single request, then
 * seed the per-message React Query cache so individual useComments hooks
 * resolve from cache instead of firing their own requests.
 */
export function useBatchCommentsPreload(messageIds: number[]) {
	const queryClient = useQueryClient();
	const prevKeyRef = useRef<string>("");

	useEffect(() => {
		if (!messageIds.length) return;

		const key = messageIds
			.slice()
			.sort((a, b) => a - b)
			.join(",");
		if (key === prevKeyRef.current) return;
		prevKeyRef.current = key;

		// Open a new gate so individual queryFns wait for us
		resetBatchGate();

		_batchTargetIds = new Set(messageIds);
		let cancelled = false;

		const promise = chatCommentsApiService
			.getBatchComments({ message_ids: messageIds })
			.then((data) => {
				if (cancelled) return;
				for (const [msgIdStr, commentList] of Object.entries(data.comments_by_message)) {
					queryClient.setQueryData(cacheKeys.comments.byMessage(Number(msgIdStr)), commentList);
				}
			})
			.catch(() => {
				// Batch failed; individual queryFns will fall through to their own fetch
			})
			.finally(() => {
				if (_batchInflight === promise) {
					_batchInflight = null;
					_batchTargetIds = new Set();
				}
			});

		_batchInflight = promise;

		// Release the gate — individual queryFns can now check _batchInflight
		_resolveBatchReady?.();

		return () => {
			cancelled = true;
			if (_batchInflight === promise) {
				_batchInflight = null;
				_batchTargetIds = new Set();
			}
		};
	}, [messageIds, queryClient]);
}
