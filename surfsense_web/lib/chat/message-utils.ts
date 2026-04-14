import type { ThreadMessageLike } from "@assistant-ui/react";
import type { MessageRecord } from "./thread-persistence";

/**
 * Convert backend message to assistant-ui ThreadMessageLike format.
 * Migrates legacy `thinking-steps` parts to `data-thinking-steps` (assistant-ui data parts).
 */
export function convertToThreadMessage(msg: MessageRecord): ThreadMessageLike {
	let content: ThreadMessageLike["content"];

	if (typeof msg.content === "string") {
		content = [{ type: "text", text: msg.content }];
	} else if (Array.isArray(msg.content)) {
		const convertedContent = msg.content
			.filter((part: unknown) => {
				if (typeof part !== "object" || part === null || !("type" in part)) return true;
				const partType = (part as { type: string }).type;
				return partType !== "mentioned-documents" && partType !== "attachments";
			})
			.map((part: unknown) => {
				if (
					typeof part === "object" &&
					part !== null &&
					"type" in part &&
					(part as { type: string }).type === "thinking-steps"
				) {
					return {
						type: "data-thinking-steps",
						data: { steps: (part as { steps: unknown[] }).steps ?? [] },
					};
				}
				return part;
			});
		content =
			convertedContent.length > 0
				? (convertedContent as ThreadMessageLike["content"])
				: [{ type: "text", text: "" }];
	} else {
		content = [{ type: "text", text: String(msg.content) }];
	}

	const metadata = (msg.author_id || msg.token_usage)
		? {
				custom: {
					...(msg.author_id && {
						author: {
							displayName: msg.author_display_name ?? null,
							avatarUrl: msg.author_avatar_url ?? null,
						},
					}),
					...(msg.token_usage && { usage: msg.token_usage }),
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
