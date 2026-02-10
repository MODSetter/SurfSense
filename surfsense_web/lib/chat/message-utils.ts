import type { ThreadMessageLike } from "@assistant-ui/react";
import type { MessageRecord } from "./thread-persistence";

/**
 * Convert backend message to assistant-ui ThreadMessageLike format
 * Filters out 'thinking-steps' part as it's handled separately via messageThinkingSteps
 */
export function convertToThreadMessage(msg: MessageRecord): ThreadMessageLike {
	let content: ThreadMessageLike["content"];

	if (typeof msg.content === "string") {
		content = [{ type: "text", text: msg.content }];
	} else if (Array.isArray(msg.content)) {
		// Filter out custom metadata parts - they're handled separately
		const filteredContent = msg.content.filter((part: unknown) => {
			if (typeof part !== "object" || part === null || !("type" in part)) return true;
			const partType = (part as { type: string }).type;
			// Filter out metadata parts not directly renderable by assistant-ui
			return (
				partType !== "thinking-steps" &&
				partType !== "mentioned-documents" &&
				partType !== "attachments"
			);
		});
		content =
			filteredContent.length > 0
				? (filteredContent as ThreadMessageLike["content"])
				: [{ type: "text", text: "" }];
	} else {
		content = [{ type: "text", text: String(msg.content) }];
	}

	// Build metadata.custom for author display in shared chats
	const metadata = msg.author_id
		? {
				custom: {
					author: {
						displayName: msg.author_display_name ?? null,
						avatarUrl: msg.author_avatar_url ?? null,
					},
				},
			}
		: undefined;

	return {
		id: `msg-${msg.id}`,
		role: msg.role,
		content,
		createdAt: new Date(msg.created_at),
		metadata,
	};
}
