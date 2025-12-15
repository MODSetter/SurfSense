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

export const membership = z.object({
	id: z.number(),
	user_id: z.string(),
	search_space_id: z.number(),
	role_id: z.number().nullable(),
	is_owner: z.boolean(),
	joined_at: z.string(),
	created_at: z.string(),
	role: role.nullable().optional(),
	user_email: z.string().nullable().optional(),
	user_is_active: z.boolean().nullable().optional(),
});

export type Role = z.infer<typeof role>;
export type Membership = z.infer<typeof membership>;
