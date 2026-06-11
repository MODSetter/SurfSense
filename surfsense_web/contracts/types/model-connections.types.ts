import { z } from "zod";

export const connectionProtocolEnum = z.enum(["OLLAMA", "OPENAI_COMPATIBLE", "ANTHROPIC"]);
export const connectionScopeEnum = z.enum(["GLOBAL", "SEARCH_SPACE", "USER"]);
export const modelSourceEnum = z.enum(["DISCOVERED", "MANUAL"]);

export const modelCapabilities = z.object({
	chat: z.boolean().optional(),
	vision: z.boolean().optional(),
	image_gen: z.boolean().optional(),
	embedding: z.boolean().optional(),
	tools: z.boolean().optional(),
});

export const modelRead = z.object({
	id: z.number(),
	connection_id: z.number(),
	model_id: z.string(),
	display_name: z.string().nullable().optional(),
	source: z.union([modelSourceEnum, z.string()]),
	capabilities: z.record(z.string(), z.any()).default({}),
	capabilities_declared: z.record(z.string(), z.any()).default({}),
	capabilities_verified: z.record(z.string(), z.any()).default({}),
	capabilities_override: z.record(z.string(), z.any()).default({}),
	embedding_dimension: z.number().nullable().optional(),
	enabled: z.boolean(),
	billing_tier: z.string().nullable().optional(),
	catalog: z.record(z.string(), z.any()).default({}),
	created_at: z.string().nullable().optional(),
});

export const connectionRead = z.object({
	id: z.number(),
	protocol: z.union([connectionProtocolEnum, z.string()]),
	litellm_provider: z.string().nullable().optional(),
	base_url: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).default({}),
	scope: z.union([connectionScopeEnum, z.string()]),
	search_space_id: z.number().nullable().optional(),
	user_id: z.string().nullable().optional(),
	enabled: z.boolean(),
	has_api_key: z.boolean(),
	last_verified_at: z.string().nullable().optional(),
	last_status: z.string().nullable().optional(),
	last_error: z.string().nullable().optional(),
	models: z.array(modelRead).default([]),
	created_at: z.string().nullable().optional(),
});

export const connectionCreateRequest = z.object({
	protocol: connectionProtocolEnum,
	litellm_provider: z.string().nullable().optional(),
	base_url: z.string().nullable().optional(),
	api_key: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).default({}),
	scope: connectionScopeEnum.default("SEARCH_SPACE"),
	search_space_id: z.number().nullable().optional(),
	enabled: z.boolean().default(true),
});

export const connectionUpdateRequest = z.object({
	litellm_provider: z.string().nullable().optional(),
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
	capabilities_override: z.record(z.string(), z.any()).optional(),
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

export const connectionListResponse = z.array(connectionRead);
export const modelListResponse = z.array(modelRead);

export type ConnectionProtocol = z.infer<typeof connectionProtocolEnum>;
export type ConnectionScope = z.infer<typeof connectionScopeEnum>;
export type ModelRead = z.infer<typeof modelRead>;
export type ConnectionRead = z.infer<typeof connectionRead>;
export type ConnectionCreateRequest = z.infer<typeof connectionCreateRequest>;
export type ConnectionUpdateRequest = z.infer<typeof connectionUpdateRequest>;
export type ModelCreateRequest = z.infer<typeof modelCreateRequest>;
export type ModelUpdateRequest = z.infer<typeof modelUpdateRequest>;
export type ModelRoles = z.infer<typeof modelRoles>;
export type VerifyConnectionResponse = z.infer<typeof verifyConnectionResponse>;
