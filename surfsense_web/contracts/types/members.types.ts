import { z } from "zod";
import { role } from "./roles.types";

export const membership = z.preprocess(
	(value) => {
		if (typeof value === "object" && value !== null && !Array.isArray(value)) {
			const record = value as Record<string, unknown>;
			if (record.search_space_id === undefined && record.workspace_id !== undefined) {
				return { ...record, search_space_id: record.workspace_id };
			}
		}
		return value;
	},
	z.object({
		id: z.number(),
		user_id: z.string(),
		search_space_id: z.number(),
		role_id: z.number().nullable(),
		is_owner: z.boolean(),
		joined_at: z.string(),
		created_at: z.string(),
		role: role.nullable().optional(),
		user_email: z.string().nullable().optional(),
		user_display_name: z.string().nullable().optional(),
		user_avatar_url: z.string().nullable().optional(),
		user_last_login: z.string().nullable().optional(),
		user_is_active: z.boolean().nullable().optional(),
	})
);

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
		role_id: z.number().nullable(),
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
 * Get my access
 */
export const getMyAccessRequest = z.object({
	search_space_id: z.number(),
});

export const getMyAccessResponse = z
	.object({
		workspace_name: z.string(),
		workspace_id: z.number(),
		is_owner: z.boolean(),
		permissions: z.array(z.string()),
		role_name: z.string().nullable(),
	})
	.transform(({ workspace_id, workspace_name, ...rest }) => ({
		...rest,
		search_space_id: workspace_id,
		search_space_name: workspace_name,
	}));

export type Membership = z.infer<typeof membership>;
export type GetMembersRequest = z.infer<typeof getMembersRequest>;
export type GetMembersResponse = z.infer<typeof getMembersResponse>;
export type UpdateMembershipRequest = z.infer<typeof updateMembershipRequest>;
export type UpdateMembershipResponse = z.infer<typeof updateMembershipResponse>;
export type DeleteMembershipRequest = z.infer<typeof deleteMembershipRequest>;
export type DeleteMembershipResponse = z.infer<typeof deleteMembershipResponse>;
export type LeaveSearchSpaceRequest = z.infer<typeof leaveSearchSpaceRequest>;
export type LeaveSearchSpaceResponse = z.infer<typeof leaveSearchSpaceResponse>;
export type GetMyAccessRequest = z.infer<typeof getMyAccessRequest>;
export type GetMyAccessResponse = z.infer<typeof getMyAccessResponse>;
