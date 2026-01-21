"use client";

import { useShape } from "@electric-sql/react";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import type { RawMessage } from "@/contracts/types/chat-messages.types";
import type { Membership } from "@/contracts/types/members.types";
import type { MessageRecord } from "@/lib/chat/thread-persistence";

const ELECTRIC_URL = process.env.NEXT_PUBLIC_ELECTRIC_URL || "http://localhost:5133";

/**
 * Member info for building author data - derived from Membership
 */
type MemberInfo = Pick<Membership, "user_display_name" | "user_avatar_url">;

/**
 * Hook to get live chat messages for real-time sync.
 * Uses Electric SQL for messages + membersAtom (API) for author info.
 */
export function useChatMessagesLive(threadId: number | null) {
	
	const {
		data: messagesData,
		isLoading: messagesLoading,
		isError: messagesError,
		error: messagesErrorDetails,
	} = useShape<RawMessage>({
		url: `${ELECTRIC_URL}/v1/shape`,
		params: {
			table: "new_chat_messages",
			where: `thread_id = ${threadId}`,
		},
	});

	
	const { data: membersData, isLoading: membersLoading } = useAtomValue(membersAtom);


	const messages = useMemo<MessageRecord[]>(() => {
		if (!messagesData) return [];

		// Build member lookup map
		const memberMap = new Map<string, MemberInfo>();
		if (membersData) {
			for (const member of membersData) {
				memberMap.set(member.user_id, {
					user_display_name: member.user_display_name,
					user_avatar_url: member.user_avatar_url,
				});
			}
		}

		// Transform raw messages to MessageRecord with author info
		return [...messagesData].map((msg): MessageRecord => {
			const author = msg.author_id ? memberMap.get(msg.author_id) : null;
			return {
				id: msg.id,
				thread_id: msg.thread_id,
				role: msg.role,
				content: msg.content,
				created_at: msg.created_at,
				author_id: msg.author_id,
				author_display_name: author?.user_display_name ?? null,
				author_avatar_url: author?.user_avatar_url ?? null,
			};
		});
	}, [messagesData, membersData]);

	return {
		messages,
		isLoading: messagesLoading || membersLoading,
		isError: messagesError,
		error: messagesError ? messagesErrorDetails : null,
	};
}
