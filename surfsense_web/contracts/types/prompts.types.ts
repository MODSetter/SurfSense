import { z } from "zod";

export type PromptMode = "transform" | "explore";

export const promptRead = z.object({
	id: z.number().nullable(),
	name: z.string(),
	prompt: z.string(),
	mode: z.enum(["transform", "explore"]),
	search_space_id: z.number().nullable().optional(),
	is_public: z.boolean().optional(),
	created_at: z.string().nullable().optional(),
	source: z.enum(["system", "custom"]),
	system_prompt_slug: z.string().nullable().optional(),
	is_modified: z.boolean().optional(),
});

export type PromptRead = z.infer<typeof promptRead>;

export const publicPromptRead = promptRead.extend({
	author_name: z.string().nullable(),
});

export type PublicPromptRead = z.infer<typeof publicPromptRead>;

export const promptsListResponse = z.array(promptRead);

export const publicPromptsListResponse = z.array(publicPromptRead);

export const promptCreateRequest = z.object({
	name: z.string().min(1).max(200),
	prompt: z.string().min(1),
	mode: z.enum(["transform", "explore"]),
	search_space_id: z.number().nullable().optional(),
	is_public: z.boolean().optional(),
});

export type PromptCreateRequest = z.infer<typeof promptCreateRequest>;

export const promptUpdateRequest = z.object({
	name: z.string().min(1).max(200).optional(),
	prompt: z.string().min(1).optional(),
	mode: z.enum(["transform", "explore"]).optional(),
	is_public: z.boolean().optional(),
});

export type PromptUpdateRequest = z.infer<typeof promptUpdateRequest>;

export const systemPromptUpdateRequest = z.object({
	name: z.string().min(1).max(200).optional(),
	prompt: z.string().min(1).optional(),
	mode: z.enum(["transform", "explore"]).optional(),
});

export type SystemPromptUpdateRequest = z.infer<typeof systemPromptUpdateRequest>;

export const promptDeleteResponse = z.object({
	success: z.boolean(),
});
