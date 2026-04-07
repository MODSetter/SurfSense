export interface VisionProviderInfo {
	value: string;
	label: string;
	example: string;
	description: string;
	apiBase?: string;
}

export const VISION_PROVIDERS: VisionProviderInfo[] = [
	{
		value: "OPENAI",
		label: "OpenAI",
		example: "gpt-4o, gpt-4o-mini",
		description: "GPT-4o vision models",
	},
	{
		value: "ANTHROPIC",
		label: "Anthropic",
		example: "claude-sonnet-4-20250514",
		description: "Claude vision models",
	},
	{
		value: "GOOGLE",
		label: "Google AI Studio",
		example: "gemini-2.5-flash, gemini-2.0-flash",
		description: "Gemini vision models",
	},
	{
		value: "AZURE_OPENAI",
		label: "Azure OpenAI",
		example: "azure/gpt-4o",
		description: "OpenAI vision models on Azure",
	},
	{
		value: "VERTEX_AI",
		label: "Google Vertex AI",
		example: "vertex_ai/gemini-2.5-flash",
		description: "Gemini vision models on Vertex AI",
	},
	{
		value: "BEDROCK",
		label: "AWS Bedrock",
		example: "bedrock/anthropic.claude-sonnet-4-20250514-v1:0",
		description: "Vision models on AWS Bedrock",
	},
	{
		value: "XAI",
		label: "xAI",
		example: "grok-2-vision",
		description: "Grok vision models",
	},
	{
		value: "OPENROUTER",
		label: "OpenRouter",
		example: "openrouter/openai/gpt-4o",
		description: "Vision models via OpenRouter",
	},
	{
		value: "OLLAMA",
		label: "Ollama",
		example: "llava, bakllava",
		description: "Local vision models via Ollama",
		apiBase: "http://localhost:11434",
	},
	{
		value: "GROQ",
		label: "Groq",
		example: "llama-4-scout-17b-16e-instruct",
		description: "Vision models on Groq",
	},
	{
		value: "TOGETHER_AI",
		label: "Together AI",
		example: "meta-llama/Llama-4-Scout-17B-16E-Instruct",
		description: "Vision models on Together AI",
	},
	{
		value: "FIREWORKS_AI",
		label: "Fireworks AI",
		example: "fireworks_ai/phi-3-vision-128k-instruct",
		description: "Vision models on Fireworks AI",
	},
	{
		value: "DEEPSEEK",
		label: "DeepSeek",
		example: "deepseek-chat",
		description: "DeepSeek vision models",
		apiBase: "https://api.deepseek.com",
	},
	{
		value: "MISTRAL",
		label: "Mistral",
		example: "pixtral-large-latest",
		description: "Pixtral vision models",
	},
	{
		value: "CUSTOM",
		label: "Custom Provider",
		example: "custom/my-vision-model",
		description: "Custom OpenAI-compatible vision endpoint",
	},
];
