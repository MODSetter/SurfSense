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

/**
 * Get roles
 */
export const getRolesRequest = z.object({
	search_space_id: z.number(),
});

export const getRolesResponse = z.array(role);

/**
 * Get role by ID
 */
export const getRoleByIdRequest = z.object({
	search_space_id: z.number(),
	role_id: z.number(),
});

export const getRoleByIdResponse = role;

/**
 * Update role
 */
export const updateRoleRequest = z.object({
	search_space_id: z.number(),
	role_id: z.number(),
	data: role.pick({
		name: true,
		description: true,
		permissions: true,
		is_default: true,
	}).partial(),
});

export const updateRoleResponse = role;

/**
 * Delete role
 */
export const deleteRoleRequest = z.object({
	search_space_id: z.number(),
	role_id: z.number(),
});

export const deleteRoleResponse = z.object({
	message: z.string(),
});

/**
 * Get members
 */
export const getMembersRequest = z.object({
	search_space_id: z.number(),
});

export const getMembersResponse = z.array(membership);

/**
 * Update membership
 */
export const updateMembershipRequest = z.object({
	search_space_id: z.number(),
	membership_id: z.number(),
	data: z.object({
		role_id: z.number(),
	}),
});

export const updateMembershipResponse = membership;

/**
 * Delete membership
 */
export const deleteMembershipRequest = z.object({
	search_space_id: z.number(),
	membership_id: z.number(),
});

export const deleteMembershipResponse = z.object({
	message: z.string(),
});

/**
 * Leave search space
 */
export const leaveSearchSpaceRequest = z.object({
	search_space_id: z.number(),
});

export const leaveSearchSpaceResponse = z.object({
	message: z.string(),
});

/**
 * Create invite
 */
export const createInviteRequest = z.object({
	search_space_id: z.number(),
	data: z.object({
		name: z.string().max(100).optional(),
		role_id: z.number().nullable().optional(),
		expires_at: z.string().nullable().optional(),
		max_uses: z.number().nullable().optional(),
	}),
});

export const createInviteResponse = invite;

/**
 * Get invites
 */
export const getInvitesRequest = z.object({
	search_space_id: z.number(),
});

export const getInvitesResponse = z.array(invite);

/**
 * Update invite
 */
export const updateInviteRequest = z.object({
	search_space_id: z.number(),
	invite_id: z.number(),
	data: z.object({
		name: z.string().max(100).optional(),
		role_id: z.number().nullable().optional(),
		expires_at: z.string().nullable().optional(),
		max_uses: z.number().nullable().optional(),
		is_active: z.boolean().optional(),
	}),
});

export const updateInviteResponse = invite;

/**
 * Delete invite
 */
export const deleteInviteRequest = z.object({
	search_space_id: z.number(),
	invite_id: z.number(),
});

export const deleteInviteResponse = z.object({
	message: z.string(),
});

/**
 * Get invite info by code
 */
export const getInviteInfoRequest = z.object({
	invite_code: z.string(),
});

export const getInviteInfoResponse = z.object({
	invite_code: z.string(),
	search_space_name: z.string(),
	role_name: z.string().nullable(),
	expires_at: z.string().nullable(),
	is_valid: z.boolean(),
});

export type Role = z.infer<typeof role>;
export type Membership = z.infer<typeof membership>;
export type Invite = z.infer<typeof invite>;
export type PermissionInfo = z.infer<typeof permissionInfo>;
export type GetPermissionsResponse = z.infer<typeof getPermissionsResponse>;
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
export type GetMembersRequest = z.infer<typeof getMembersRequest>;
export type GetMembersResponse = z.infer<typeof getMembersResponse>;
export type UpdateMembershipRequest = z.infer<typeof updateMembershipRequest>;
export type UpdateMembershipResponse = z.infer<typeof updateMembershipResponse>;
export type DeleteMembershipRequest = z.infer<typeof deleteMembershipRequest>;
export type DeleteMembershipResponse = z.infer<typeof deleteMembershipResponse>;
export type LeaveSearchSpaceRequest = z.infer<typeof leaveSearchSpaceRequest>;
export type LeaveSearchSpaceResponse = z.infer<typeof leaveSearchSpaceResponse>;
export type CreateInviteRequest = z.infer<typeof createInviteRequest>;
export type CreateInviteResponse = z.infer<typeof createInviteResponse>;
export type GetInvitesRequest = z.infer<typeof getInvitesRequest>;
export type GetInvitesResponse = z.infer<typeof getInvitesResponse>;
export type UpdateInviteRequest = z.infer<typeof updateInviteRequest>;
export type UpdateInviteResponse = z.infer<typeof updateInviteResponse>;
export type DeleteInviteRequest = z.infer<typeof deleteInviteRequest>;
export type DeleteInviteResponse = z.infer<typeof deleteInviteResponse>;
export type GetInviteInfoRequest = z.infer<typeof getInviteInfoRequest>;
export type GetInviteInfoResponse = z.infer<typeof getInviteInfoResponse>;
