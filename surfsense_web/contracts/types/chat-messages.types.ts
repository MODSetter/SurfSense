import { z } from "zod";

/**
 * Raw message from database (Electric SQL sync)
 */
export const rawMessage = z.object({
	id: z.number(),
	thread_id: z.number(),
	role: z.string(),
	content: z.unknown(),
	author_id: z.string().nullable(),
	created_at: z.string(),
});

export type RawMessage = z.infer<typeof rawMessage>;
