import { z } from "zod";

export const user = z.object({
	id: z.uuid(),
	email: z.email(),
	is_active: z.boolean(),
	is_superuser: z.boolean(),
	is_verified: z.boolean(),
	pages_limit: z.number(),
	pages_used: z.number(),
});

/**
 * Get current user
 */
export const getMeResponse = user;

export type User = z.infer<typeof user>;
export type GetMeResponse = z.infer<typeof getMeResponse>;
