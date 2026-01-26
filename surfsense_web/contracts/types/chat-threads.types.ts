import { z } from "zod";

/**
 * Toggle public share
 */
export const togglePublicShareRequest = z.object({
	thread_id: z.number(),
	enabled: z.boolean(),
});

export const togglePublicShareResponse = z.object({
	enabled: z.boolean(),
	public_url: z.string().nullable(),
	share_token: z.string().nullable(),
});

// Type exports
export type TogglePublicShareRequest = z.infer<typeof togglePublicShareRequest>;
export type TogglePublicShareResponse = z.infer<typeof togglePublicShareResponse>;
