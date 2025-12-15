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

export const invite = z.object({
	id: z.number(),
	name: z.string().max(100).nullable().optional(),
	invite_code: z.string(),
	search_space_id: z.number(),
	created_by_id: z.string().nullable(),
	role_id: z.number().nullable(),
	expires_at: z.string().nullable(),
	max_uses: z.number().nullable(),
	uses_count: z.number(),
	is_active: z.boolean(),
	created_at: z.string(),
	role: role.nullable().optional(),
});

export const permissionInfo = z.object({
	value: z.string(),
	name: z.string(),
	category: z.string(),
});

/**
 * Get permissions
 */
export const getPermissionsResponse = z.object({
	permissions: z.array(permissionInfo),
});

/**
 * Create role
 */
export const createRoleRequest = z.object({
	search_space_id: z.number(),
	data: role.pick({
		name: true,
		description: true,
		permissions: true,
		is_default: true,
	}),
});

export const createRoleResponse = role;

export type Role = z.infer<typeof role>;
export type Membership = z.infer<typeof membership>;
export type Invite = z.infer<typeof invite>;
export type PermissionInfo = z.infer<typeof permissionInfo>;
export type GetPermissionsResponse = z.infer<typeof getPermissionsResponse>;
export type CreateRoleRequest = z.infer<typeof createRoleRequest>;
export type CreateRoleResponse = z.infer<typeof createRoleResponse>;
