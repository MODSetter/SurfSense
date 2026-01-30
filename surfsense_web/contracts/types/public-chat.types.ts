import { z } from "zod";

/**
 * Author info for public chat
 */
export const publicAuthor = z.object({
	display_name: z.string().nullable(),
	avatar_url: z.string().nullable(),
});

/**
 * Message in a public chat
 */
export const publicChatMessage = z.object({
	role: z.string(),
	content: z.unknown(),
	author: publicAuthor.nullable(),
	created_at: z.string(),
});

/**
 * Thread info for public chat
 */
export const publicChatThread = z.object({
	title: z.string(),
	created_at: z.string(),
});

/**
 * Get public chat
 */
export const getPublicChatRequest = z.object({
	share_token: z.string(),
});

export const getPublicChatResponse = z.object({
	thread: publicChatThread,
	messages: z.array(publicChatMessage),
});

/**
 * Clone public chat
 */
export const clonePublicChatRequest = z.object({
	share_token: z.string(),
});

export const clonePublicChatResponse = z.object({
	thread_id: z.number(),
	search_space_id: z.number(),
});

// Type exports
export type PublicAuthor = z.infer<typeof publicAuthor>;
export type PublicChatMessage = z.infer<typeof publicChatMessage>;
export type PublicChatThread = z.infer<typeof publicChatThread>;
export type GetPublicChatRequest = z.infer<typeof getPublicChatRequest>;
export type GetPublicChatResponse = z.infer<typeof getPublicChatResponse>;
export type ClonePublicChatRequest = z.infer<typeof clonePublicChatRequest>;
export type ClonePublicChatResponse = z.infer<typeof clonePublicChatResponse>;
