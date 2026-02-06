import { z } from "zod";

/**
 * LiteLLM Provider enum - all supported LLM providers
 */
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

export type LiteLLMProvider = z.infer<typeof liteLLMProviderEnum>;

/**
 * NewLLMConfig - combines LLM model settings with prompt configuration
 */
export const newLLMConfig = z.object({
	id: z.number(),
	name: z.string().max(100),
	description: z.string().max(500).nullable().optional(),

	// LLM Model Configuration
	provider: liteLLMProviderEnum,
	custom_provider: z.string().max(100).nullable().optional(),
	model_name: z.string().max(100),
	api_key: z.string(),
	api_base: z.string().max(500).nullable().optional(),
	litellm_params: z.record(z.string(), z.any()).nullable().optional(),

	// Prompt Configuration
	system_instructions: z.string().default(""),
	use_default_system_instructions: z.boolean().default(true),
	citations_enabled: z.boolean().default(true),

	// Metadata
	created_at: z.string(),
	search_space_id: z.number(),
});

/**
 * Public version without api_key (for list views)
 */
export const newLLMConfigPublic = newLLMConfig.omit({ api_key: true });

/**
 * Create NewLLMConfig
 */
export const createNewLLMConfigRequest = newLLMConfig.omit({
	id: true,
	created_at: true,
});

export const createNewLLMConfigResponse = newLLMConfig;

/**
 * Get NewLLMConfigs list
 */
export const getNewLLMConfigsRequest = z.object({
	search_space_id: z.number(),
	skip: z.number().optional(),
	limit: z.number().optional(),
});

export const getNewLLMConfigsResponse = z.array(newLLMConfig);

/**
 * Get single NewLLMConfig
 */
export const getNewLLMConfigRequest = z.object({
	id: z.number(),
});

export const getNewLLMConfigResponse = newLLMConfig;

/**
 * Update NewLLMConfig
 */
export const updateNewLLMConfigRequest = z.object({
	id: z.number(),
	data: newLLMConfig
		.omit({
			id: true,
			created_at: true,
			search_space_id: true,
		})
		.partial(),
});

export const updateNewLLMConfigResponse = newLLMConfig;

/**
 * Delete NewLLMConfig
 */
export const deleteNewLLMConfigRequest = z.object({
	id: z.number(),
});

export const deleteNewLLMConfigResponse = z.object({
	message: z.string(),
	id: z.number(),
});

/**
 * Get default system instructions
 */
export const getDefaultSystemInstructionsResponse = z.object({
	default_system_instructions: z.string(),
});

/**
 * Global NewLLMConfig - from YAML, has negative IDs
 * ID 0 is reserved for "Auto" mode which uses LiteLLM Router for load balancing
 */
export const globalNewLLMConfig = z.object({
	id: z.number(), // 0 for Auto mode, negative IDs for global configs
	name: z.string(),
	description: z.string().nullable().optional(),

	// LLM Model Configuration (no api_key)
	provider: z.string(), // String because YAML doesn't enforce enum, "AUTO" for Auto mode
	custom_provider: z.string().nullable().optional(),
	model_name: z.string(),
	api_base: z.string().nullable().optional(),
	litellm_params: z.record(z.string(), z.any()).nullable().optional(),

	// Prompt Configuration
	system_instructions: z.string().default(""),
	use_default_system_instructions: z.boolean().default(true),
	citations_enabled: z.boolean().default(true),

	is_global: z.literal(true),
	is_auto_mode: z.boolean().optional().default(false), // True only for Auto mode (ID 0)
});

export const getGlobalNewLLMConfigsResponse = z.array(globalNewLLMConfig);

// =============================================================================
// Image Generation Config (separate table from NewLLMConfig)
// =============================================================================

/**
 * ImageGenProvider enum - only providers that support image generation
 * See: https://docs.litellm.ai/docs/image_generation#supported-providers
 */
export const imageGenProviderEnum = z.enum([
	"OPENAI",
	"AZURE_OPENAI",
	"GOOGLE",
	"VERTEX_AI",
	"BEDROCK",
	"RECRAFT",
	"OPENROUTER",
	"XINFERENCE",
	"NSCALE",
]);

export type ImageGenProvider = z.infer<typeof imageGenProviderEnum>;

/**
 * ImageGenerationConfig - user-created image gen model configs
 * Separate from NewLLMConfig: no system_instructions, no citations_enabled.
 */
export const imageGenerationConfig = z.object({
	id: z.number(),
	name: z.string().max(100),
	description: z.string().max(500).nullable().optional(),
	provider: imageGenProviderEnum,
	custom_provider: z.string().max(100).nullable().optional(),
	model_name: z.string().max(100),
	api_key: z.string(),
	api_base: z.string().max(500).nullable().optional(),
	api_version: z.string().max(50).nullable().optional(),
	litellm_params: z.record(z.string(), z.any()).nullable().optional(),
	created_at: z.string(),
	search_space_id: z.number(),
});

export const createImageGenConfigRequest = imageGenerationConfig.omit({
	id: true,
	created_at: true,
});

export const createImageGenConfigResponse = imageGenerationConfig;

export const getImageGenConfigsResponse = z.array(imageGenerationConfig);

export const updateImageGenConfigRequest = z.object({
	id: z.number(),
	data: imageGenerationConfig
		.omit({ id: true, created_at: true, search_space_id: true })
		.partial(),
});

export const updateImageGenConfigResponse = imageGenerationConfig;

export const deleteImageGenConfigResponse = z.object({
	message: z.string(),
	id: z.number(),
});

/**
 * Global Image Generation Config - from YAML, has negative IDs
 * ID 0 is reserved for "Auto" mode (LiteLLM Router load balancing)
 */
export const globalImageGenConfig = z.object({
	id: z.number(),
	name: z.string(),
	description: z.string().nullable().optional(),
	provider: z.string(),
	custom_provider: z.string().nullable().optional(),
	model_name: z.string(),
	api_base: z.string().nullable().optional(),
	api_version: z.string().nullable().optional(),
	litellm_params: z.record(z.string(), z.any()).nullable().optional(),
	is_global: z.literal(true),
	is_auto_mode: z.boolean().optional().default(false),
});

export const getGlobalImageGenConfigsResponse = z.array(globalImageGenConfig);

// =============================================================================
// LLM Preferences (Role Assignments)
// =============================================================================

/**
 * LLM Preferences schemas - for role assignments
 * image_generation uses image_generation_config_id (not llm_id)
 */
export const llmPreferences = z.object({
	agent_llm_id: z.union([z.number(), z.null()]).optional(),
	document_summary_llm_id: z.union([z.number(), z.null()]).optional(),
	image_generation_config_id: z.union([z.number(), z.null()]).optional(),
	agent_llm: z.union([z.record(z.string(), z.unknown()), z.null()]).optional(),
	document_summary_llm: z.union([z.record(z.string(), z.unknown()), z.null()]).optional(),
	image_generation_config: z.union([z.record(z.string(), z.unknown()), z.null()]).optional(),
});

/**
 * Get LLM preferences
 */
export const getLLMPreferencesRequest = z.object({
	search_space_id: z.number(),
});

export const getLLMPreferencesResponse = llmPreferences;

/**
 * Update LLM preferences
 */
export const updateLLMPreferencesRequest = z.object({
	search_space_id: z.number(),
	data: llmPreferences.pick({
		agent_llm_id: true,
		document_summary_llm_id: true,
		image_generation_config_id: true,
	}),
});

export const updateLLMPreferencesResponse = llmPreferences;

// =============================================================================
// Type Exports
// =============================================================================

export type NewLLMConfig = z.infer<typeof newLLMConfig>;
export type NewLLMConfigPublic = z.infer<typeof newLLMConfigPublic>;
export type CreateNewLLMConfigRequest = z.infer<typeof createNewLLMConfigRequest>;
export type CreateNewLLMConfigResponse = z.infer<typeof createNewLLMConfigResponse>;
export type GetNewLLMConfigsRequest = z.infer<typeof getNewLLMConfigsRequest>;
export type GetNewLLMConfigsResponse = z.infer<typeof getNewLLMConfigsResponse>;
export type GetNewLLMConfigRequest = z.infer<typeof getNewLLMConfigRequest>;
export type GetNewLLMConfigResponse = z.infer<typeof getNewLLMConfigResponse>;
export type UpdateNewLLMConfigRequest = z.infer<typeof updateNewLLMConfigRequest>;
export type UpdateNewLLMConfigResponse = z.infer<typeof updateNewLLMConfigResponse>;
export type DeleteNewLLMConfigRequest = z.infer<typeof deleteNewLLMConfigRequest>;
export type DeleteNewLLMConfigResponse = z.infer<typeof deleteNewLLMConfigResponse>;
export type GetDefaultSystemInstructionsResponse = z.infer<
	typeof getDefaultSystemInstructionsResponse
>;
export type GlobalNewLLMConfig = z.infer<typeof globalNewLLMConfig>;
export type GetGlobalNewLLMConfigsResponse = z.infer<typeof getGlobalNewLLMConfigsResponse>;
export type ImageGenerationConfig = z.infer<typeof imageGenerationConfig>;
export type CreateImageGenConfigRequest = z.infer<typeof createImageGenConfigRequest>;
export type CreateImageGenConfigResponse = z.infer<typeof createImageGenConfigResponse>;
export type GetImageGenConfigsResponse = z.infer<typeof getImageGenConfigsResponse>;
export type UpdateImageGenConfigRequest = z.infer<typeof updateImageGenConfigRequest>;
export type UpdateImageGenConfigResponse = z.infer<typeof updateImageGenConfigResponse>;
export type DeleteImageGenConfigResponse = z.infer<typeof deleteImageGenConfigResponse>;
export type GlobalImageGenConfig = z.infer<typeof globalImageGenConfig>;
export type GetGlobalImageGenConfigsResponse = z.infer<typeof getGlobalImageGenConfigsResponse>;
export type LLMPreferences = z.infer<typeof llmPreferences>;
export type GetLLMPreferencesRequest = z.infer<typeof getLLMPreferencesRequest>;
export type GetLLMPreferencesResponse = z.infer<typeof getLLMPreferencesResponse>;
export type UpdateLLMPreferencesRequest = z.infer<typeof updateLLMPreferencesRequest>;
export type UpdateLLMPreferencesResponse = z.infer<typeof updateLLMPreferencesResponse>;
