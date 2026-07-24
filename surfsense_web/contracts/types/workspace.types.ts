import { z } from "zod";
import { paginationQueryParams } from ".";
import { llmSetupStatus } from "./model-connections.types";

export const workspace = z.object({
	id: z.number(),
	name: z.string(),
	description: z.string().nullable(),
	created_at: z.string(),
	user_id: z.string(),
	citations_enabled: z.boolean(),
	api_access_enabled: z.boolean().optional().default(false),
	qna_custom_instructions: z.string().nullable(),
	shared_memory_md: z.string().nullable().optional(),
	member_count: z.number(),
	is_owner: z.boolean(),
});

/**
 * Get workspaces
 */
export const getWorkspacesRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			owned_only: z.boolean().optional(),
		})
		.nullish(),
});

export const getWorkspacesResponse = z.array(workspace);

/**
 * Workspace limits
 */
export const workspaceLimits = z.object({
	max_workspaces_per_user: z.number(),
});

/**
 * Create workspace
 */
export const createWorkspaceRequest = workspace.pick({ name: true, description: true }).extend({
	citations_enabled: z.boolean().prefault(true).optional(),
	qna_custom_instructions: z.string().nullable().optional(),
});

export const createWorkspaceResponse = workspace
	.omit({ member_count: true, is_owner: true })
	.extend({ llm_setup: llmSetupStatus.nullable().optional() });

/**
 * Get workspace
 */
export const getWorkspaceRequest = workspace.pick({ id: true });

export const getWorkspaceResponse = workspace.omit({ member_count: true, is_owner: true });

/**
 * Update workspace
 */
export const updateWorkspaceRequest = z.object({
	id: z.number(),
	data: workspace
		.pick({
			name: true,
			description: true,
			citations_enabled: true,
			api_access_enabled: true,
			qna_custom_instructions: true,
		})
		.partial(),
});

export const updateWorkspaceResponse = workspace.omit({ member_count: true, is_owner: true });

export const updateWorkspaceApiAccessRequest = z.object({
	id: z.number(),
	api_access_enabled: z.boolean(),
});

export const updateWorkspaceApiAccessResponse = workspace.omit({
	member_count: true,
	is_owner: true,
});

/**
 * Delete workspace
 */
export const deleteWorkspaceRequest = workspace.pick({ id: true });

export const deleteWorkspaceResponse = z.object({
	message: z.literal("Workspace deleted successfully"),
});

/**
 * Leave workspace (for non-owners)
 */
export const leaveWorkspaceResponse = z.object({
	message: z.literal("Successfully left the workspace"),
});

// Inferred types
export type Workspace = z.infer<typeof workspace>;
export type WorkspaceLimits = z.infer<typeof workspaceLimits>;
export type GetWorkspacesRequest = z.infer<typeof getWorkspacesRequest>;
export type GetWorkspacesResponse = z.infer<typeof getWorkspacesResponse>;
export type CreateWorkspaceRequest = z.infer<typeof createWorkspaceRequest>;
export type CreateWorkspaceResponse = z.infer<typeof createWorkspaceResponse>;
export type GetWorkspaceRequest = z.infer<typeof getWorkspaceRequest>;
export type GetWorkspaceResponse = z.infer<typeof getWorkspaceResponse>;
export type UpdateWorkspaceRequest = z.infer<typeof updateWorkspaceRequest>;
export type UpdateWorkspaceResponse = z.infer<typeof updateWorkspaceResponse>;
export type UpdateWorkspaceApiAccessRequest = z.infer<typeof updateWorkspaceApiAccessRequest>;
export type UpdateWorkspaceApiAccessResponse = z.infer<typeof updateWorkspaceApiAccessResponse>;
export type DeleteWorkspaceRequest = z.infer<typeof deleteWorkspaceRequest>;
export type DeleteWorkspaceResponse = z.infer<typeof deleteWorkspaceResponse>;
