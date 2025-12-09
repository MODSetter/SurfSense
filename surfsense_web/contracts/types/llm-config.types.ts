import { z } from "zod";

// LiteLLM Provider enum matching backend
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

// Base LLM Config schema
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

// Inferred types
export type LLMConfig = z.infer<typeof llmConfig>;
export type LiteLLMProvider = z.infer<typeof liteLLMProviderEnum>;
