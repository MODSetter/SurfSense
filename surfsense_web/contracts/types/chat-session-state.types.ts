import { z } from "zod";

/**
 * Chat session state for live collaboration.
 * Tracks which user the AI is currently responding to.
 */
export const chatSessionState = z.object({
	id: z.number(),
	thread_id: z.number(),
	ai_responding_to_user_id: z.string().uuid().nullable(),
	updated_at: z.string(),
});

/**
 * User currently being responded to by the AI.
 */
export const respondingUser = z.object({
	id: z.string().uuid(),
	display_name: z.string().nullable(),
	email: z.string(),
});

export type ChatSessionState = z.infer<typeof chatSessionState>;
export type RespondingUser = z.infer<typeof respondingUser>;
