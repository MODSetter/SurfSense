import { z } from "zod";
import { paginationQueryParams } from ".";

export const searchSpace = z.object({
	id: z.number(),
	name: z.string(),
	description: z.string().nullable(),
	created_at: z.string(),
	user_id: z.string(),
	citations_enabled: z.boolean(),
	qna_custom_instructions: z.string().nullable(),
	member_count: z.number(),
	is_owner: z.boolean(),
});

/**
 * Get search spaces
 */
export const getSearchSpacesRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			owned_only: z.boolean().optional(),
		})
		.nullish(),
});

export const getSearchSpacesResponse = z.array(searchSpace);

/**
 * Create search space
 */
export const createSearchSpaceRequest = searchSpace.pick({ name: true, description: true }).extend({
	citations_enabled: z.boolean().prefault(true).optional(),
	qna_custom_instructions: z.string().nullable().optional(),
});

export const createSearchSpaceResponse = searchSpace.omit({ member_count: true, is_owner: true });

/**
 * Get search space
 */
export const getSearchSpaceRequest = searchSpace.pick({ id: true });

export const getSearchSpaceResponse = searchSpace.omit({ member_count: true, is_owner: true });

/**
 * Update search space
 */
export const updateSearchSpaceRequest = z.object({
	id: z.number(),
	data: searchSpace
		.pick({ name: true, description: true, citations_enabled: true, qna_custom_instructions: true })
		.partial(),
});

export const updateSearchSpaceResponse = searchSpace.omit({ member_count: true, is_owner: true });

/**
 * Delete search space
 */
export const deleteSearchSpaceRequest = searchSpace.pick({ id: true });

export const deleteSearchSpaceResponse = z.object({
	message: z.literal("Search space deleted successfully"),
});

/**
 * Leave search space (for non-owners)
 */
export const leaveSearchSpaceResponse = z.object({
	message: z.literal("Successfully left the search space"),
});

// Inferred types
export type SearchSpace = z.infer<typeof searchSpace>;
export type GetSearchSpacesRequest = z.infer<typeof getSearchSpacesRequest>;
export type GetSearchSpacesResponse = z.infer<typeof getSearchSpacesResponse>;
export type CreateSearchSpaceRequest = z.infer<typeof createSearchSpaceRequest>;
export type CreateSearchSpaceResponse = z.infer<typeof createSearchSpaceResponse>;
export type GetSearchSpaceRequest = z.infer<typeof getSearchSpaceRequest>;
export type GetSearchSpaceResponse = z.infer<typeof getSearchSpaceResponse>;
export type UpdateSearchSpaceRequest = z.infer<typeof updateSearchSpaceRequest>;
export type UpdateSearchSpaceResponse = z.infer<typeof updateSearchSpaceResponse>;
export type DeleteSearchSpaceRequest = z.infer<typeof deleteSearchSpaceRequest>;
export type DeleteSearchSpaceResponse = z.infer<typeof deleteSearchSpaceResponse>;
