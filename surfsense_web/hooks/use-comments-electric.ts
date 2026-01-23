"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { Author, Comment, CommentReply } from "@/contracts/types/chat-comments.types";
import type { Membership } from "@/contracts/types/members.types";
import type { SyncHandle } from "@/lib/electric/client";
import { useElectricClient } from "@/lib/electric/context";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// Debounce delay for stream updates (ms)
const STREAM_UPDATE_DEBOUNCE_MS = 100;

// Raw comment from PGlite local database
interface RawCommentRow {
	id: number;
	message_id: number;
	thread_id: number;
	parent_id: number | null;
	author_id: string | null;
	content: string;
	created_at: string;
	updated_at: string;
}

// Regex pattern to match @[uuid] mentions (matches backend MENTION_PATTERN)
const MENTION_PATTERN = /@\[([0-9a-fA-F-]{36})\]/g;

type MemberInfo = Pick<Membership, "user_display_name" | "user_avatar_url" | "user_email">;

/**
 * Render mentions in content by replacing @[uuid] with @{DisplayName}
 */
function renderMentions(content: string, memberMap: Map<string, MemberInfo>): string {
	return content.replace(MENTION_PATTERN, (match, uuid) => {
		const member = memberMap.get(uuid);
		if (member?.user_display_name) {
			return `@{${member.user_display_name}}`;
		}
		return match;
	});
}

/**
 * Build member lookup map from membersData
 */
function buildMemberMap(membersData: Membership[] | undefined): Map<string, MemberInfo> {
	const map = new Map<string, MemberInfo>();
	if (membersData) {
		for (const m of membersData) {
			map.set(m.user_id, {
				user_display_name: m.user_display_name,
				user_avatar_url: m.user_avatar_url,
				user_email: m.user_email,
			});
		}
	}
	return map;
}

/**
 * Build author object from member data
 */
function buildAuthor(authorId: string | null, memberMap: Map<string, MemberInfo>): Author | null {
	if (!authorId) return null;
	const m = memberMap.get(authorId);
	if (!m) return null;
	return {
		id: authorId,
		display_name: m.user_display_name ?? null,
		avatar_url: m.user_avatar_url ?? null,
		email: m.user_email ?? "",
	};
}

/**
 * Check if a comment has been edited by comparing timestamps.
 * Uses a small threshold to handle precision differences.
 */
function isEdited(createdAt: string, updatedAt: string): boolean {
	const created = new Date(createdAt).getTime();
	const updated = new Date(updatedAt).getTime();
	// Consider edited if updated_at is more than 1 second after created_at
	return updated - created > 1000;
}

/**
 * Transform raw comment to CommentReply
 */
function transformReply(
	raw: RawCommentRow,
	memberMap: Map<string, MemberInfo>,
	currentUserId: string | undefined,
	isOwner: boolean
): CommentReply {
	return {
		id: raw.id,
		content: raw.content,
		content_rendered: renderMentions(raw.content, memberMap),
		author: buildAuthor(raw.author_id, memberMap),
		created_at: raw.created_at,
		updated_at: raw.updated_at,
		is_edited: isEdited(raw.created_at, raw.updated_at),
		can_edit: currentUserId === raw.author_id,
		can_delete: currentUserId === raw.author_id || isOwner,
	};
}

/**
 * Transform raw comments to Comment with replies
 */
function transformComments(
	rawComments: RawCommentRow[],
	memberMap: Map<string, MemberInfo>,
	currentUserId: string | undefined,
	isOwner: boolean
): Map<number, Comment[]> {
	// Group comments by message_id
	const byMessage = new Map<
		number,
		{ topLevel: RawCommentRow[]; replies: Map<number, RawCommentRow[]> }
	>();

	for (const raw of rawComments) {
		if (!byMessage.has(raw.message_id)) {
			byMessage.set(raw.message_id, { topLevel: [], replies: new Map() });
		}
		const group = byMessage.get(raw.message_id)!;

		if (raw.parent_id === null) {
			group.topLevel.push(raw);
		} else {
			if (!group.replies.has(raw.parent_id)) {
				group.replies.set(raw.parent_id, []);
			}
			group.replies.get(raw.parent_id)!.push(raw);
		}
	}

	// Transform to Comment objects grouped by message_id
	const result = new Map<number, Comment[]>();

	for (const [messageId, group] of byMessage) {
		const comments: Comment[] = group.topLevel.map((raw) => {
			const replies = (group.replies.get(raw.id) || [])
				.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
				.map((r) => transformReply(r, memberMap, currentUserId, isOwner));

			return {
				id: raw.id,
				message_id: raw.message_id,
				content: raw.content,
				content_rendered: renderMentions(raw.content, memberMap),
				author: buildAuthor(raw.author_id, memberMap),
				created_at: raw.created_at,
				updated_at: raw.updated_at,
				is_edited: isEdited(raw.created_at, raw.updated_at),
				can_edit: currentUserId === raw.author_id,
				can_delete: currentUserId === raw.author_id || isOwner,
				reply_count: replies.length,
				replies,
			};
		});

		// Sort by created_at
		comments.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
		result.set(messageId, comments);
	}

	return result;
}

/**
 * Hook for syncing comments with Electric SQL real-time sync.
 *
 * Syncs ALL comments for a thread in ONE subscription, then updates
 * React Query cache for each message. This avoids N subscriptions for N messages.
 *
 * @param threadId - The thread ID to sync comments for
 */
export function useCommentsElectric(threadId: number | null) {
	const electricClient = useElectricClient();
	const queryClient = useQueryClient();

	const { data: membersData } = useAtomValue(membersAtom);
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: myAccess } = useAtomValue(myAccessAtom);

	const memberMap = useMemo(() => buildMemberMap(membersData), [membersData]);
	const currentUserId = currentUser?.id;
	const isOwner = myAccess?.is_owner ?? false;

	// Use refs for values needed in live query callback to avoid stale closures
	const memberMapRef = useRef(memberMap);
	const currentUserIdRef = useRef(currentUserId);
	const isOwnerRef = useRef(isOwner);
	const queryClientRef = useRef(queryClient);

	// Keep refs updated
	useEffect(() => {
		memberMapRef.current = memberMap;
		currentUserIdRef.current = currentUserId;
		isOwnerRef.current = isOwner;
		queryClientRef.current = queryClient;
	}, [memberMap, currentUserId, isOwner, queryClient]);

	const syncHandleRef = useRef<SyncHandle | null>(null);
	const liveQueryRef = useRef<{ unsubscribe: () => void } | null>(null);
	const syncKeyRef = useRef<string | null>(null);
	const streamUpdateDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// Stable callback that uses refs for fresh values
	const updateReactQueryCache = useCallback((rows: RawCommentRow[]) => {
		const commentsByMessage = transformComments(
			rows,
			memberMapRef.current,
			currentUserIdRef.current,
			isOwnerRef.current
		);

		for (const [messageId, comments] of commentsByMessage) {
			const cacheKey = cacheKeys.comments.byMessage(messageId);
			queryClientRef.current.setQueryData(cacheKey, {
				comments,
				total_count: comments.length,
			});
		}
	}, []);

	useEffect(() => {
		if (!threadId || !electricClient) {
			return;
		}

		const syncKey = `comments_${threadId}`;
		if (syncKeyRef.current === syncKey) {
			return;
		}

		// Capture in local variable for use in async functions
		const client = electricClient;

		let mounted = true;
		syncKeyRef.current = syncKey;

		async function startSync() {
			try {
				const handle = await client.syncShape({
					table: "chat_comments",
					where: `thread_id = ${threadId}`,
					columns: [
						"id",
						"message_id",
						"thread_id",
						"parent_id",
						"author_id",
						"content",
						"created_at",
						"updated_at",
					],
					primaryKey: ["id"],
				});

				if (!handle.isUpToDate && handle.initialSyncPromise) {
					try {
						await Promise.race([
							handle.initialSyncPromise,
							new Promise((resolve) => setTimeout(resolve, 3000)),
						]);
					} catch {
						// Initial sync timeout - continue anyway
					}
				}

				if (!mounted) {
					handle.unsubscribe();
					return;
				}

				syncHandleRef.current = handle;

				// Fetch initial comments and update cache
				await fetchAndUpdateCache();

				// Set up live query for real-time updates
				await setupLiveQuery();

				// Subscribe to the sync stream for real-time updates from Electric SQL
				// This ensures we catch updates even if PGlite live query misses them
				if (handle.stream) {
					const stream = handle.stream as {
						subscribe?: (callback: (messages: unknown[]) => void) => void;
					};
					if (typeof stream.subscribe === "function") {
						stream.subscribe((messages: unknown[]) => {
							if (!mounted) return;
							// When Electric sync receives new data, refresh from PGlite
							// This handles cases where live query might miss the update
							if (messages && messages.length > 0) {
								// Debounce the refresh to avoid excessive queries
								if (streamUpdateDebounceRef.current) {
									clearTimeout(streamUpdateDebounceRef.current);
								}
								streamUpdateDebounceRef.current = setTimeout(() => {
									if (mounted) {
										fetchAndUpdateCache();
									}
								}, STREAM_UPDATE_DEBOUNCE_MS);
							}
						});
					}
				}
			} catch {
				// Sync failed - will retry on next mount
			}
		}

		async function fetchAndUpdateCache() {
			try {
				const result = await client.db.query<RawCommentRow>(
					`SELECT id, message_id, thread_id, parent_id, author_id, content, created_at, updated_at 
					 FROM chat_comments 
					 WHERE thread_id = $1 
					 ORDER BY created_at ASC`,
					[threadId]
				);

				if (mounted && result.rows) {
					updateReactQueryCache(result.rows);
				}
			} catch {
				// Query failed - data will be fetched from API
			}
		}

		async function setupLiveQuery() {
			try {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const db = client.db as any;

				if (db.live?.query && typeof db.live.query === "function") {
					const liveQuery = await db.live.query(
						`SELECT id, message_id, thread_id, parent_id, author_id, content, created_at, updated_at 
						 FROM chat_comments 
						 WHERE thread_id = $1 
						 ORDER BY created_at ASC`,
						[threadId]
					);

					if (!mounted) {
						liveQuery.unsubscribe?.();
						return;
					}

					// Set initial results
					if (liveQuery.initialResults?.rows) {
						updateReactQueryCache(liveQuery.initialResults.rows);
					} else if (liveQuery.rows) {
						updateReactQueryCache(liveQuery.rows);
					}

					// Subscribe to changes
					if (typeof liveQuery.subscribe === "function") {
						liveQuery.subscribe((result: { rows: RawCommentRow[] }) => {
							if (mounted && result.rows) {
								updateReactQueryCache(result.rows);
							}
						});
					}

					if (typeof liveQuery.unsubscribe === "function") {
						liveQueryRef.current = liveQuery;
					}
				}
			} catch {
				// Live query setup failed - will use initial fetch only
			}
		}

		startSync();

		return () => {
			mounted = false;
			syncKeyRef.current = null;

			// Clear debounce timeout
			if (streamUpdateDebounceRef.current) {
				clearTimeout(streamUpdateDebounceRef.current);
				streamUpdateDebounceRef.current = null;
			}

			if (syncHandleRef.current) {
				syncHandleRef.current.unsubscribe();
				syncHandleRef.current = null;
			}
			if (liveQueryRef.current) {
				liveQueryRef.current.unsubscribe();
				liveQueryRef.current = null;
			}
		};
	}, [threadId, electricClient, updateReactQueryCache]);
}
