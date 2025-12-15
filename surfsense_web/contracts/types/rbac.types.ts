import { z } from "zod";

export const role = z.object({
	id: z.number(),
	name: z.string().min(1).max(100),
	description: z.string().max(500).nullable(),
	permissions: z.array(z.string()),
	is_default: z.boolean(),
	is_system_role: z.boolean(),
	search_space_id: z.number(),
	created_at: z.string(),
});

export type Role = z.infer<typeof role>;