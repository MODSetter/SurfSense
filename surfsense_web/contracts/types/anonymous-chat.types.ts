import { z } from "zod";

export const anonModel = z.object({
	id: z.number(),
	name: z.string(),
	description: z.string().nullable().optional(),
	provider: z.string(),
	model_name: z.string(),
	billing_tier: z.string().default("free"),
	is_premium: z.boolean().default(false),
	seo_slug: z.string().nullable().optional(),
	seo_enabled: z.boolean().default(false),
	seo_title: z.string().nullable().optional(),
	seo_description: z.string().nullable().optional(),
	quota_reserve_tokens: z.number().nullable().optional(),
});

export const getAnonModelsResponse = z.array(anonModel);

export const getAnonModelResponse = anonModel;

export const anonQuotaResponse = z.object({
	used: z.number(),
	limit: z.number(),
	remaining: z.number(),
	status: z.string(),
	warning_threshold: z.number(),
	captcha_required: z.boolean().default(false),
});

export const anonChatRequest = z.object({
	model_slug: z.string().max(100),
	messages: z
		.array(
			z.object({
				role: z.enum(["system", "user", "assistant"]),
				content: z.string(),
			})
		)
		.min(1),
	disabled_tools: z.array(z.string()).optional(),
	turnstile_token: z.string().optional(),
});

export type AnonModel = z.infer<typeof anonModel>;
export type GetAnonModelsResponse = z.infer<typeof getAnonModelsResponse>;
export type GetAnonModelResponse = z.infer<typeof getAnonModelResponse>;
export type AnonQuotaResponse = z.infer<typeof anonQuotaResponse>;
export type AnonChatRequest = z.infer<typeof anonChatRequest>;
