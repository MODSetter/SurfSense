import { z } from "zod";

const roleBase = z.object({
	id: z.number(),
	name: z.string().min(1).max(100),
	description: z.string().max(500).nullable(),
	permissions: z.array(z.string()),
	is_default: z.boolean(),
	is_system_role: z.boolean(),
	workspace_id: z.number(),
	created_at: z.string(),
});

export const role = roleBase;

/**
 * Create role
 */
export const createRoleRequest = z.object({
	workspace_id: z.number(),
	data: roleBase.pick({
		name: true,
		description: true,
		permissions: true,
		is_default: true,
	}),
});

export const createRoleResponse = role;

/**
 * Get roles
 */
export const getRolesRequest = z.object({
	workspace_id: z.number(),
});

export const getRolesResponse = z.array(role);

/**
 * Get role by ID
 */
export const getRoleByIdRequest = z.object({
	workspace_id: z.number(),
	role_id: z.number(),
});

export const getRoleByIdResponse = role;

/**
 * Update role
 */
export const updateRoleRequest = z.object({
	workspace_id: z.number(),
	role_id: z.number(),
	data: roleBase
		.pick({
			name: true,
			description: true,
			permissions: true,
			is_default: true,
		})
		.partial(),
});

export const updateRoleResponse = role;

/**
 * Delete role
 */
export const deleteRoleRequest = z.object({
	workspace_id: z.number(),
	role_id: z.number(),
});

export const deleteRoleResponse = z.object({
	message: z.string(),
});

export type Role = z.infer<typeof role>;
export type CreateRoleRequest = z.infer<typeof createRoleRequest>;
export type CreateRoleResponse = z.infer<typeof createRoleResponse>;
export type GetRolesRequest = z.infer<typeof getRolesRequest>;
export type GetRolesResponse = z.infer<typeof getRolesResponse>;
export type GetRoleByIdRequest = z.infer<typeof getRoleByIdRequest>;
export type GetRoleByIdResponse = z.infer<typeof getRoleByIdResponse>;
export type UpdateRoleRequest = z.infer<typeof updateRoleRequest>;
export type UpdateRoleResponse = z.infer<typeof updateRoleResponse>;
export type DeleteRoleRequest = z.infer<typeof deleteRoleRequest>;
export type DeleteRoleResponse = z.infer<typeof deleteRoleResponse>;
