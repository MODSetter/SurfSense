import { json, number, string, table } from "@rocicorp/zero";

export const newChatMessageTable = table("new_chat_messages")
	.columns({
		id: number(),
		role: string(),
		content: json(),
		threadId: number().from("thread_id"),
		authorId: string().optional().from("author_id"),
		createdAt: number().from("created_at"),
		// Per-turn correlation id sourced from ``configurable.turn_id``
		// at streaming time. Required by the inline Revert button's
		// (chat_turn_id, tool_name, position) fallback in tool-fallback.tsx
		// — without it the live-collab Zero sync would clobber the
		// metadata we set during streaming and the button would vanish
		// the moment Zero re-syncs after the stream finishes.
		turnId: string().optional().from("turn_id"),
	})
	.primaryKey("id");

export const chatCommentTable = table("chat_comments")
	.columns({
		id: number(),
		messageId: number().from("message_id"),
		threadId: number().from("thread_id"),
		parentId: number().optional().from("parent_id"),
		authorId: string().optional().from("author_id"),
		content: string(),
		createdAt: number().from("created_at"),
		updatedAt: number().from("updated_at"),
	})
	.primaryKey("id");

export const chatSessionStateTable = table("chat_session_state")
	.columns({
		id: number(),
		threadId: number().from("thread_id"),
		aiRespondingToUserId: string().optional().from("ai_responding_to_user_id"),
		updatedAt: number().from("updated_at"),
	})
	.primaryKey("id");
