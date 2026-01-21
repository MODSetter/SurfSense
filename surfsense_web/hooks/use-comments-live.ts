"use client";

import { useShape } from "@electric-sql/react";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { Comment, CommentReply, Author } from "@/contracts/types/chat-comments.types";
import type { Membership } from "@/contracts/types/members.types";
import type { RawComment } from "@/contracts/types/chat-comments.types";

const ELECTRIC_URL = process.env.NEXT_PUBLIC_ELECTRIC_URL || "http://localhost:5133";

// Regex pattern to match @[uuid] mentions (matches backend MENTION_PATTERN)
const MENTION_PATTERN = /@\[([0-9a-fA-F-]{36})\]/g;

/**
 * Member info for building author objects - derived from Membership
 */
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
 * Hook to get live comments for a specific message.
 * Uses Electric SQL for comments + membersAtom (API) for author info.
 * Returns data matching the existing Comment type.
 */
export function useCommentsLive(messageId: number | null) {
	const {
		data: commentsData,
		isLoading: commentsLoading,
		isError: commentsError,
		error: commentsErrorDetails,
	} = useShape<RawComment>({
		url: `${ELECTRIC_URL}/v1/shape`,
		params: {
			table: "chat_comments",
			where: `message_id = ${messageId}`,
		},
	});

	const { data: membersData, isLoading: membersLoading } = useAtomValue(membersAtom);
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: myAccess } = useAtomValue(myAccessAtom);

	const comments = useMemo<Comment[]>(() => {
		if (!commentsData) return [];

		// Build member lookup map
		const memberMap = new Map<string, MemberInfo>();
		if (membersData) {
			for (const member of membersData) {
				memberMap.set(member.user_id, {
					user_display_name: member.user_display_name,
					user_avatar_url: member.user_avatar_url,
					user_email: member.user_email,
				});
			}
		}

		const currentUserId = currentUser?.id;
		const isOwnerOrAdmin = myAccess?.is_owner ?? false;

		// Build author object from member data
		const buildAuthor = (authorId: string | null): Author | null => {
			if (!authorId) return null;
			const member = memberMap.get(authorId);
			if (!member) return null;
			return {
				id: authorId,
				display_name: member.user_display_name ?? null,
				avatar_url: member.user_avatar_url ?? null,
				email: member.user_email ?? "",
			};
		};

		// Transform raw comment to CommentReply
		const transformToReply = (raw: RawComment): CommentReply => {
			const isEdited = raw.created_at !== raw.updated_at;
			const isAuthor = currentUserId === raw.author_id;

			return {
				id: raw.id,
				content: raw.content,
				content_rendered: renderMentions(raw.content, memberMap),
				author: buildAuthor(raw.author_id),
				created_at: raw.created_at,
				updated_at: raw.updated_at,
				is_edited: isEdited,
				can_edit: isAuthor,
				can_delete: isAuthor || isOwnerOrAdmin,
			};
		};

		// Separate top-level comments and replies
		const topLevelRaw: RawComment[] = [];
		const repliesMap = new Map<number, RawComment[]>();

		for (const raw of commentsData) {
			if (raw.parent_id === null) {
				topLevelRaw.push(raw);
			} else {
				const replies = repliesMap.get(raw.parent_id) || [];
				replies.push(raw);
				repliesMap.set(raw.parent_id, replies);
			}
		}

		// Transform top-level comments to Comment type
		const transformToComment = (raw: RawComment): Comment => {
			const isEdited = raw.created_at !== raw.updated_at;
			const isAuthor = currentUserId === raw.author_id;
			const rawReplies = repliesMap.get(raw.id) || [];
			const replies = rawReplies.map(transformToReply);

			return {
				id: raw.id,
				message_id: raw.message_id,
				content: raw.content,
				content_rendered: renderMentions(raw.content, memberMap),
				author: buildAuthor(raw.author_id),
				created_at: raw.created_at,
				updated_at: raw.updated_at,
				is_edited: isEdited,
				can_edit: isAuthor,
				can_delete: isAuthor || isOwnerOrAdmin,
				reply_count: replies.length,
				replies,
			};
		};

		return topLevelRaw.map(transformToComment);
	}, [commentsData, membersData, currentUser?.id, myAccess?.is_owner]);

	return {
		comments,
		commentCount: commentsData?.length ?? 0,
		isLoading: commentsLoading || membersLoading,
		isError: commentsError,
		error: commentsError ? commentsErrorDetails : null,
	};
}
