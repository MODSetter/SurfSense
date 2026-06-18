import { z } from "zod";

export const connectionScopeEnum = z.enum(["GLOBAL", "SEARCH_SPACE", "USER"]);
export const modelSourceEnum = z.enum(["DISCOVERED", "MANUAL"]);

export const modelRead = z.object({
	id: z.number(),
	connection_id: z.number(),
	model_id: z.string(),
	display_name: z.string().nullable().optional(),
	source: z.union([modelSourceEnum, z.string()]),
	supports_chat: z.boolean().nullable().optional(),
	max_input_tokens: z.number().nullable().optional(),
	supports_image_input: z.boolean().nullable().optional(),
	supports_tools: z.boolean().nullable().optional(),
	supports_image_generation: z.boolean().nullable().optional(),
	capabilities_override: z.record(z.string(), z.any()).default({}),
	enabled: z.boolean(),
	billing_tier: z.string().nullable().optional(),
	catalog: z.record(z.string(), z.any()).default({}),
	created_at: z.string().nullable().optional(),
});

export const connectionRead = z.object({
	id: z.number(),
	provider: z.string(),
	base_url: z.string().nullable().optional(),
	api_key: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).default({}),
	scope: z.union([connectionScopeEnum, z.string()]),
	search_space_id: z.number().nullable().optional(),
	user_id: z.string().nullable().optional(),
	enabled: z.boolean(),
	has_api_key: z.boolean(),
	models: z.array(modelRead).default([]),
	created_at: z.string().nullable().optional(),
});

export const modelSelection = z.object({
	model_id: z.string().min(1),
	display_name: z.string().nullable().optional(),
	source: z.union([modelSourceEnum, z.string()]).default("DISCOVERED"),
	supports_chat: z.boolean().nullable().optional(),
	max_input_tokens: z.number().nullable().optional(),
	supports_image_input: z.boolean().nullable().optional(),
	supports_tools: z.boolean().nullable().optional(),
	supports_image_generation: z.boolean().nullable().optional(),
	enabled: z.boolean().default(false),
	metadata: z.record(z.string(), z.any()).default({}),
});

export const modelPreviewRead = modelSelection;

export const connectionCreateRequest = z.object({
	provider: z.string().min(1),
	base_url: z.string().nullable().optional(),
	api_key: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).default({}),
	scope: connectionScopeEnum.default("SEARCH_SPACE"),
	search_space_id: z.number().nullable().optional(),
	enabled: z.boolean().default(true),
	models: z.array(modelSelection).default([]),
});

export const modelTestPreviewRequest = connectionCreateRequest.extend({
	model_id: z.string().min(1),
});

export const connectionUpdateRequest = z.object({
	provider: z.string().nullable().optional(),
	base_url: z.string().nullable().optional(),
	api_key: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).optional(),
	enabled: z.boolean().optional(),
});

export const modelCreateRequest = z.object({
	model_id: z.string().min(1),
	display_name: z.string().nullable().optional(),
});

export const modelUpdateRequest = z.object({
	display_name: z.string().nullable().optional(),
	enabled: z.boolean().optional(),
	supports_chat: z.boolean().nullable().optional(),
	max_input_tokens: z.number().nullable().optional(),
	supports_image_input: z.boolean().nullable().optional(),
	supports_tools: z.boolean().nullable().optional(),
	supports_image_generation: z.boolean().nullable().optional(),
	capabilities_override: z.record(z.string(), z.any()).optional(),
});

export const modelsBulkUpdateRequest = z.object({
	model_ids: z.array(z.number()).min(1).max(1000),
	enabled: z.boolean(),
});

export const verifyConnectionResponse = z.object({
	status: z.string(),
	ok: z.boolean(),
	message: z.string().default(""),
});

export const modelRoles = z.object({
	chat_model_id: z.number().nullable().optional(),
	vision_model_id: z.number().nullable().optional(),
	image_gen_model_id: z.number().nullable().optional(),
});

export const globalLlmConfigStatus = z.object({
	exists: z.boolean(),
});

export const modelProviderRead = z.object({
	provider: z.string(),
	transport: z.string(),
	discovery: z.string(),
	default_base_url: z.string().nullable().optional(),
	base_url_required: z.boolean(),
	auth_style: z.string(),
	local_only: z.boolean().default(false),
});

export const modelProviderListResponse = z.array(modelProviderRead);

export const connectionListResponse = z.array(connectionRead);
export const modelListResponse = z.array(modelRead);
export const modelPreviewListResponse = z.array(modelPreviewRead);

export type ConnectionScope = z.infer<typeof connectionScopeEnum>;
export type ModelRead = z.infer<typeof modelRead>;
export type ModelPreviewRead = z.infer<typeof modelPreviewRead>;
export type ModelSelection = z.infer<typeof modelSelection>;
export type ConnectionRead = z.infer<typeof connectionRead>;
export type ConnectionCreateRequest = z.infer<typeof connectionCreateRequest>;
export type ModelTestPreviewRequest = z.infer<typeof modelTestPreviewRequest>;
export type ConnectionUpdateRequest = z.infer<typeof connectionUpdateRequest>;
export type ModelCreateRequest = z.infer<typeof modelCreateRequest>;
export type ModelUpdateRequest = z.infer<typeof modelUpdateRequest>;
export type ModelsBulkUpdateRequest = z.infer<typeof modelsBulkUpdateRequest>;
export type ModelRoles = z.infer<typeof modelRoles>;
export type GlobalLlmConfigStatus = z.infer<typeof globalLlmConfigStatus>;
export type VerifyConnectionResponse = z.infer<typeof verifyConnectionResponse>;
export type ModelProviderRead = z.infer<typeof modelProviderRead>;
