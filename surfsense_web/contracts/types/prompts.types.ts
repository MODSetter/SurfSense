import { z } from "zod";

export type PromptMode = "transform" | "explore";

export const promptRead = z.object({
	id: z.number(),
	name: z.string(),
	prompt: z.string(),
	mode: z.enum(["transform", "explore"]),
	icon: z.string().nullable(),
	search_space_id: z.number().nullable(),
	created_at: z.string(),
});

export type PromptRead = z.infer<typeof promptRead>;

export const promptsListResponse = z.array(promptRead);

export const promptCreateRequest = z.object({
	name: z.string().min(1).max(200),
	prompt: z.string().min(1),
	mode: z.enum(["transform", "explore"]),
	icon: z.string().max(50).nullable().optional(),
	search_space_id: z.number().nullable().optional(),
});

export type PromptCreateRequest = z.infer<typeof promptCreateRequest>;

export const promptUpdateRequest = z.object({
	name: z.string().min(1).max(200).optional(),
	prompt: z.string().min(1).optional(),
	mode: z.enum(["transform", "explore"]).optional(),
	icon: z.string().max(50).nullable().optional(),
});

export type PromptUpdateRequest = z.infer<typeof promptUpdateRequest>;

export const promptDeleteResponse = z.object({
	success: z.boolean(),
});
