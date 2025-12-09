export interface LLMProvider {
	value: string;
	label: string;
	example: string;
	description: string;
	apiBase?: string;
}

export const LLM_PROVIDERS: LLMProvider[] = [
	{
		value: "OPENAI",
		label: "OpenAI",
		example: "gpt-4o, gpt-4o-mini, o1, o3-mini",
		description: "Industry-leading GPT models",
	},
	{
		value: "ANTHROPIC",
		label: "Anthropic",
		example: "claude-3-5-sonnet, claude-3-opus, claude-4-sonnet",
		description: "Claude models with strong reasoning",
	},
	{
		value: "GOOGLE",
		label: "Google (Gemini)",
		example: "gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-pro",
		description: "Gemini models with multimodal capabilities",
	},
	{
		value: "AZURE_OPENAI",
		label: "Azure OpenAI",
		example: "azure/gpt-4o, azure/gpt-4o-mini",
		description: "OpenAI models on Azure",
	},
	{
		value: "BEDROCK",
		label: "AWS Bedrock",
		example: "anthropic.claude-3-5-sonnet, meta.llama3-70b",
		description: "Foundation models on AWS",
	},
	{
		value: "VERTEX_AI",
		label: "Google Vertex AI",
		example: "vertex_ai/claude-3-5-sonnet, vertex_ai/gemini-2.5-pro",
		description: "Models on Google Cloud Vertex AI",
	},
	{
		value: "GROQ",
		label: "Groq",
		example: "groq/llama-3.3-70b-versatile, groq/mixtral-8x7b",
		description: "Ultra-fast inference",
	},
	{
		value: "COHERE",
		label: "Cohere",
		example: "command-a-03-2025, command-r-plus",
		description: "Enterprise NLP models",
	},
	{
		value: "MISTRAL",
		label: "Mistral AI",
		example: "mistral-large-latest, mistral-medium-latest",
		description: "European open-source models",
	},
	{
		value: "DEEPSEEK",
		label: "DeepSeek",
		example: "deepseek-chat, deepseek-reasoner",
		description: "High-performance reasoning models",
		apiBase: "https://api.deepseek.com",
	},
	{
		value: "XAI",
		label: "xAI (Grok)",
		example: "grok-4, grok-3, grok-3-mini",
		description: "Grok models from xAI",
	},
	{
		value: "OPENROUTER",
		label: "OpenRouter",
		example: "openrouter/anthropic/claude-4-opus",
		description: "Unified API for multiple providers",
	},
	{
		value: "TOGETHER_AI",
		label: "Together AI",
		example: "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
		description: "Fast open-source models",
	},
	{
		value: "FIREWORKS_AI",
		label: "Fireworks AI",
		example: "fireworks_ai/accounts/fireworks/models/llama-v3p3-70b-instruct",
		description: "Scalable inference platform",
	},
	{
		value: "REPLICATE",
		label: "Replicate",
		example: "replicate/meta/llama-3-70b-instruct",
		description: "ML model hosting platform",
	},
	{
		value: "PERPLEXITY",
		label: "Perplexity",
		example: "perplexity/sonar-pro, perplexity/sonar-reasoning",
		description: "Search-augmented models",
	},
	{
		value: "OLLAMA",
		label: "Ollama",
		example: "ollama/llama3.1, ollama/mistral",
		description: "Run models locally",
		apiBase: "http://localhost:11434",
	},
	{
		value: "ALIBABA_QWEN",
		label: "Alibaba Qwen",
		example: "dashscope/qwen-plus, dashscope/qwen-turbo",
		description: "Qwen series models",
		apiBase: "https://dashscope.aliyuncs.com/compatible-mode/v1",
	},
	{
		value: "MOONSHOT",
		label: "Moonshot (Kimi)",
		example: "moonshot/kimi-latest, moonshot/kimi-k2-thinking",
		description: "Kimi AI models",
		apiBase: "https://api.moonshot.cn/v1",
	},
	{
		value: "ZHIPU",
		label: "Zhipu (GLM)",
		example: "openrouter/z-ai/glm-4.6",
		description: "GLM series models",
		apiBase: "https://open.bigmodel.cn/api/paas/v4",
	},
	{
		value: "ANYSCALE",
		label: "Anyscale",
		example: "anyscale/meta-llama/Meta-Llama-3-70B-Instruct",
		description: "Ray-based inference platform",
	},
	{
		value: "DEEPINFRA",
		label: "DeepInfra",
		example: "deepinfra/meta-llama/Meta-Llama-3.3-70B-Instruct",
		description: "Serverless GPU inference",
	},
	{
		value: "CEREBRAS",
		label: "Cerebras",
		example: "cerebras/llama-3.3-70b, cerebras/qwen-3-32b",
		description: "Fastest inference with Wafer-Scale Engine",
	},
	{
		value: "SAMBANOVA",
		label: "SambaNova",
		example: "sambanova/Meta-Llama-3.3-70B-Instruct",
		description: "AI inference platform",
	},
	{
		value: "AI21",
		label: "AI21 Labs",
		example: "jamba-1.5-large, jamba-1.5-mini",
		description: "Jamba series models",
	},
	{
		value: "CLOUDFLARE",
		label: "Cloudflare Workers AI",
		example: "cloudflare/@cf/meta/llama-2-7b-chat",
		description: "AI on Cloudflare edge network",
	},
	{
		value: "DATABRICKS",
		label: "Databricks",
		example: "databricks/databricks-meta-llama-3-3-70b-instruct",
		description: "Databricks Model Serving",
	},
	{
		value: "CUSTOM",
		label: "Custom Provider",
		example: "your-custom-model",
		description: "Custom OpenAI-compatible endpoint",
	},
];
