import { z } from "zod";

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

export type LLMConfig = z.infer<typeof llmConfig>;
export type LiteLLMProvider = z.infer<typeof liteLLMProviderEnum>;
export type GlobalLLMConfig = z.infer<typeof globalLLMConfig>;
export type GetGlobalLLMConfigsResponse = z.infer<typeof getGlobalLLMConfigsResponse>;
export type CreateLLMConfigRequest = z.infer<typeof createLLMConfigRequest>;
export type CreateLLMConfigResponse = z.infer<typeof createLLMConfigResponse>;
