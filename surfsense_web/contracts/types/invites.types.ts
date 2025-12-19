import { z } from "zod";
import { role } from "./roles.types";

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
	search_space_name: z.string(),
	role_name: z.string().nullable(),
	is_valid: z.boolean(),
	message: z.string().nullable(),
});

/**
 * Accept invite
 */
export const acceptInviteRequest = z.object({
	invite_code: z.string(),
});

export const acceptInviteResponse = z.object({
	message: z.string(),
	search_space_id: z.number(),
	search_space_name: z.string(),
	role_name: z.string().nullable(),
});

export type Invite = z.infer<typeof invite>;
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
export type AcceptInviteRequest = z.infer<typeof acceptInviteRequest>;
export type AcceptInviteResponse = z.infer<typeof acceptInviteResponse>;
