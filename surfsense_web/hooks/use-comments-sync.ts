"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { Author, Comment, CommentReply } from "@/contracts/types/chat-comments.types";
import type { Membership } from "@/contracts/types/members.types";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queries } from "@/zero/queries";

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

const MENTION_PATTERN = /@\[([0-9a-fA-F-]{36})\]/g;

type MemberInfo = Pick<Membership, "user_display_name" | "user_avatar_url" | "user_email">;

function renderMentions(content: string, memberMap: Map<string, MemberInfo>): string {
	return content.replace(MENTION_PATTERN, (match, uuid) => {
		const member = memberMap.get(uuid);
		if (member?.user_display_name) {
			return `@{${member.user_display_name}}`;
		}
		return match;
	});
}

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

function isEdited(createdAt: string, updatedAt: string): boolean {
	const created = new Date(createdAt).getTime();
	const updated = new Date(updatedAt).getTime();
	return updated - created > 1000;
}

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

function transformComments(
	rawComments: RawCommentRow[],
	memberMap: Map<string, MemberInfo>,
	currentUserId: string | undefined,
	isOwner: boolean
): Map<number, Comment[]> {
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

	const result = new Map<number, Comment[]>();

	for (const [messageId, group] of byMessage) {
		const comments: Comment[] = group.topLevel.map((raw) => {
			const replies = (group.replies.get(raw.id) ?? []).toSorted(
				(a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
			)
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

		comments.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
		result.set(messageId, comments);
	}

	return result;
}

/**
 * Syncs comments for a thread via Zero real-time sync.
 *
 * Syncs ALL comments for a thread in ONE subscription, then updates
 * React Query cache for each message. This avoids N subscriptions for N messages.
 */
export function useCommentsSync(threadId: number | null) {
	const queryClient = useQueryClient();

	const { data: membersData } = useAtomValue(membersAtom);
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: myAccess } = useAtomValue(myAccessAtom);

	const memberMap = useMemo(() => buildMemberMap(membersData), [membersData]);
	const currentUserId = currentUser?.id;
	const isOwner = myAccess?.is_owner ?? false;

	const memberMapRef = useRef(memberMap);
	const currentUserIdRef = useRef(currentUserId);
	const isOwnerRef = useRef(isOwner);
	const queryClientRef = useRef(queryClient);

	useEffect(() => {
		memberMapRef.current = memberMap;
		currentUserIdRef.current = currentUserId;
		isOwnerRef.current = isOwner;
		queryClientRef.current = queryClient;
	}, [memberMap, currentUserId, isOwner, queryClient]);

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

	const [data] = useQuery(queries.comments.byThread({ threadId: threadId ?? -1 }));

	useEffect(() => {
		if (!threadId || !data) return;

		const rows: RawCommentRow[] = data.map((c) => ({
			id: c.id,
			message_id: c.messageId,
			thread_id: c.threadId,
			parent_id: c.parentId ?? null,
			author_id: c.authorId ?? null,
			content: c.content,
			created_at: new Date(c.createdAt).toISOString(),
			updated_at: new Date(c.updatedAt).toISOString(),
		}));

		updateReactQueryCache(rows);
	}, [threadId, data, updateReactQueryCache]);
}
