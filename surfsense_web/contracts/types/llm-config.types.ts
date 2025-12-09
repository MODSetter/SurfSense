import { z } from "zod";
import { paginationQueryParams } from ".";

export const liteLLMProviderEnum = z.enum([
	"OPENAI",
	"ANTHROPIC",
	"GOOGLE",
	"AZURE_OPENAI",
	"BEDROCK",
	"VERTEX_AI",
	"GROQ",
	"COHERE",
	"MISTRAL",
	"DEEPSEEK",
	"XAI",
	"OPENROUTER",
	"TOGETHER_AI",
	"FIREWORKS_AI",
	"REPLICATE",
	"PERPLEXITY",
	"OLLAMA",
	"ALIBABA_QWEN",
	"MOONSHOT",
	"ZHIPU",
	"ANYSCALE",
	"DEEPINFRA",
	"CEREBRAS",
	"SAMBANOVA",
	"AI21",
	"CLOUDFLARE",
	"DATABRICKS",
	"COMETAPI",
	"HUGGINGFACE",
	"CUSTOM",
]);

export const llmConfig = z.object({
	id: z.number(),
	name: z.string().max(100),
	provider: liteLLMProviderEnum,
	custom_provider: z.string().max(100).nullable().optional(),
	model_name: z.string().max(100),
	api_key: z.string(),
	api_base: z.string().max(500).nullable().optional(),
	language: z.string().max(50).nullable().optional().default("English"),
	litellm_params: z.record(z.string(), z.any()).nullable().optional(),
	search_space_id: z.number(),
	created_at: z.string(),
	updated_at: z.string(),
});

export const globalLLMConfig = llmConfig
	.pick({
		id: true,
		name: true,
		custom_provider: true,
		model_name: true,
		api_base: true,
		language: true,
		litellm_params: true,
	})
	.extend({
		provider: z.string(),
		is_global: z.literal(true),
	});

/**
 * Get global LLM configs
 */
export const getGlobalLLMConfigsResponse = z.array(globalLLMConfig);

/**
 * Create LLM config
 */
export const createLLMConfigRequest = llmConfig.pick({
	name: true,
	provider: true,
	custom_provider: true,
	model_name: true,
	api_key: true,
	api_base: true,
	language: true,
	litellm_params: true,
	search_space_id: true,
});

export const createLLMConfigResponse = llmConfig;

/**
 * Get LLM configs
 */
export const getLLMConfigsRequest = z.object({
	queryParams: paginationQueryParams
		.pick({ skip: true, limit: true })
		.extend({
			search_space_id: z.number().or(z.string()),
		})
		.nullish(),
});

export const getLLMConfigsResponse = z.array(llmConfig);

/**
 * Get LLM config by ID
 */
export const getLLMConfigRequest = llmConfig.pick({ id: true });

export const getLLMConfigResponse = llmConfig;

/**
 * Update LLM config
 */
export const updateLLMConfigRequest = z.object({
	id: z.number(),
	data: llmConfig
		.pick({
			name: true,
			provider: true,
			custom_provider: true,
			model_name: true,
			api_key: true,
			api_base: true,
			language: true,
			litellm_params: true,
		})
		.partial(),
});

export const updateLLMConfigResponse = llmConfig;

/**
 * Delete LLM config
 */
export const deleteLLMConfigRequest = llmConfig.pick({ id: true });

export const deleteLLMConfigResponse = z.object({
	message: z.literal("LLM configuration deleted successfully"),
});

/**
 * LLM Preferences schemas
 */
export const llmPreferences = z.object({
	long_context_llm_id: z.number().nullable().optional(),
	fast_llm_id: z.number().nullable().optional(),
	strategic_llm_id: z.number().nullable().optional(),
	long_context_llm: llmConfig.nullable().optional(),
	fast_llm: llmConfig.nullable().optional(),
	strategic_llm: llmConfig.nullable().optional(),
});

/**
 * Get LLM preferences
 */
export const getLLMPreferencesRequest = z.object({
	search_space_id: z.number(),
});

export const getLLMPreferencesResponse = llmPreferences;

export type LLMConfig = z.infer<typeof llmConfig>;
export type LiteLLMProvider = z.infer<typeof liteLLMProviderEnum>;
export type GlobalLLMConfig = z.infer<typeof globalLLMConfig>;
export type GetGlobalLLMConfigsResponse = z.infer<typeof getGlobalLLMConfigsResponse>;
export type CreateLLMConfigRequest = z.infer<typeof createLLMConfigRequest>;
export type CreateLLMConfigResponse = z.infer<typeof createLLMConfigResponse>;
export type GetLLMConfigsRequest = z.infer<typeof getLLMConfigsRequest>;
export type GetLLMConfigsResponse = z.infer<typeof getLLMConfigsResponse>;
export type GetLLMConfigRequest = z.infer<typeof getLLMConfigRequest>;
export type GetLLMConfigResponse = z.infer<typeof getLLMConfigResponse>;
export type UpdateLLMConfigRequest = z.infer<typeof updateLLMConfigRequest>;
export type UpdateLLMConfigResponse = z.infer<typeof updateLLMConfigResponse>;
export type DeleteLLMConfigRequest = z.infer<typeof deleteLLMConfigRequest>;
export type DeleteLLMConfigResponse = z.infer<typeof deleteLLMConfigResponse>;
export type LLMPreferences = z.infer<typeof llmPreferences>;
export type GetLLMPreferencesRequest = z.infer<typeof getLLMPreferencesRequest>;
export type GetLLMPreferencesResponse = z.infer<typeof getLLMPreferencesResponse>;
