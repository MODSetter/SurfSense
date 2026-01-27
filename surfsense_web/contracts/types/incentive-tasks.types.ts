import { z } from "zod";

/**
 * Incentive task type enum - matches backend IncentiveTaskType
 */
export const incentiveTaskTypeEnum = z.enum(["GITHUB_STAR"]);

/**
 * Single incentive task info schema
 */
export const incentiveTaskInfo = z.object({
	task_type: incentiveTaskTypeEnum,
	title: z.string(),
	description: z.string(),
	pages_reward: z.number(),
	action_url: z.string(),
	completed: z.boolean(),
	completed_at: z.string().nullable(),
});

/**
 * Response schema for getting all incentive tasks
 */
export const getIncentiveTasksResponse = z.object({
	tasks: z.array(incentiveTaskInfo),
	total_pages_earned: z.number(),
});

/**
 * Response schema for completing a task successfully
 */
export const completeTaskSuccessResponse = z.object({
	success: z.literal(true),
	message: z.string(),
	pages_awarded: z.number(),
	new_pages_limit: z.number(),
});

/**
 * Response schema when task was already completed
 */
export const completeTaskAlreadyCompletedResponse = z.object({
	success: z.literal(false),
	message: z.string(),
	completed_at: z.string(),
});

/**
 * Union response for complete task endpoint
 */
export const completeTaskResponse = z.union([
	completeTaskSuccessResponse,
	completeTaskAlreadyCompletedResponse,
]);

// =============================================================================
// Inferred types
// =============================================================================

export type IncentiveTaskTypeEnum = z.infer<typeof incentiveTaskTypeEnum>;
export type IncentiveTaskInfo = z.infer<typeof incentiveTaskInfo>;
export type GetIncentiveTasksResponse = z.infer<typeof getIncentiveTasksResponse>;
export type CompleteTaskSuccessResponse = z.infer<typeof completeTaskSuccessResponse>;
export type CompleteTaskAlreadyCompletedResponse = z.infer<
	typeof completeTaskAlreadyCompletedResponse
>;
export type CompleteTaskResponse = z.infer<typeof completeTaskResponse>;
