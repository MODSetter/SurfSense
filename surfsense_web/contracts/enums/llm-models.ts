export interface LLMModel {
	value: string;
	label: string;
	provider: string;
	contextWindow?: string;
}

// Comprehensive LLM models database organized by provider
export const LLM_MODELS: LLMModel[] = [
	// OpenAI
	{
		value: "gpt-4o",
		label: "GPT-4o",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4o-mini",
		label: "GPT-4o Mini",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4o-2024-11-20",
		label: "GPT-4o (Nov 2024)",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4o-2024-08-06",
		label: "GPT-4o (Aug 2024)",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4o-2024-05-13",
		label: "GPT-4o (May 2024)",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4-turbo",
		label: "GPT-4 Turbo",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{ value: "gpt-4", label: "GPT-4", provider: "OPENAI", contextWindow: "8K" },
	{
		value: "gpt-3.5-turbo",
		label: "GPT-3.5 Turbo",
		provider: "OPENAI",
		contextWindow: "16K",
	},
	{ value: "o1", label: "O1", provider: "OPENAI", contextWindow: "200K" },
	{
		value: "o1-mini",
		label: "O1 Mini",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{
		value: "o1-preview",
		label: "O1 Preview",
		provider: "OPENAI",
		contextWindow: "128K",
	},
	{ value: "o3", label: "O3", provider: "OPENAI", contextWindow: "200K" },
	{
		value: "o3-mini",
		label: "O3 Mini",
		provider: "OPENAI",
		contextWindow: "200K",
	},
	{
		value: "o4-mini",
		label: "O4 Mini",
		provider: "OPENAI",
		contextWindow: "200K",
	},
	{
		value: "gpt-4.1",
		label: "GPT-4.1",
		provider: "OPENAI",
		contextWindow: "1M",
	},
	{
		value: "gpt-4.1-mini",
		label: "GPT-4.1 Mini",
		provider: "OPENAI",
		contextWindow: "1M",
	},
	{
		value: "gpt-4.1-nano",
		label: "GPT-4.1 Nano",
		provider: "OPENAI",
		contextWindow: "1M",
	},
	{ value: "gpt-5", label: "GPT-5", provider: "OPENAI", contextWindow: "272K" },
	{
		value: "gpt-5-mini",
		label: "GPT-5 Mini",
		provider: "OPENAI",
		contextWindow: "272K",
	},
	{
		value: "gpt-5-nano",
		label: "GPT-5 Nano",
		provider: "OPENAI",
		contextWindow: "272K",
	},
	{
		value: "chatgpt-4o-latest",
		label: "ChatGPT-4o Latest",
		provider: "OPENAI",
		contextWindow: "128K",
	},

	// Anthropic
	{
		value: "claude-3-5-sonnet-20241022",
		label: "Claude 3.5 Sonnet",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-3-7-sonnet-20250219",
		label: "Claude 3.7 Sonnet",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-4-sonnet-20250514",
		label: "Claude 4 Sonnet",
		provider: "ANTHROPIC",
		contextWindow: "1M",
	},
	{
		value: "claude-4-opus-20250514",
		label: "Claude 4 Opus",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-3-5-haiku-20241022",
		label: "Claude 3.5 Haiku",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-haiku-4-5-20251001",
		label: "Claude Haiku 4.5",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-3-opus-20240229",
		label: "Claude 3 Opus",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-3-haiku-20240307",
		label: "Claude 3 Haiku",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-sonnet-4-5-20250929",
		label: "Claude Sonnet 4.5",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},
	{
		value: "claude-opus-4-1-20250805",
		label: "Claude Opus 4.1",
		provider: "ANTHROPIC",
		contextWindow: "200K",
	},

	// Google (Gemini)
	{
		value: "gemini-2.5-flash",
		label: "Gemini 2.5 Flash",
		provider: "GOOGLE",
		contextWindow: "1M",
	},
	{
		value: "gemini-2.5-pro",
		label: "Gemini 2.5 Pro",
		provider: "GOOGLE",
		contextWindow: "1M",
	},
	{
		value: "gemini-2.0-flash",
		label: "Gemini 2.0 Flash",
		provider: "GOOGLE",
		contextWindow: "1M",
	},
	{
		value: "gemini-2.0-flash-lite",
		label: "Gemini 2.0 Flash Lite",
		provider: "GOOGLE",
		contextWindow: "1M",
	},
	{
		value: "gemini-1.5-flash",
		label: "Gemini 1.5 Flash",
		provider: "GOOGLE",
		contextWindow: "1M",
	},
	{
		value: "gemini-1.5-pro",
		label: "Gemini 1.5 Pro",
		provider: "GOOGLE",
		contextWindow: "2M",
	},
	{
		value: "gemini-pro",
		label: "Gemini Pro",
		provider: "GOOGLE",
		contextWindow: "33K",
	},
	{
		value: "gemini-pro-vision",
		label: "Gemini Pro Vision",
		provider: "GOOGLE",
		contextWindow: "16K",
	},

	// DeepSeek
	{
		value: "deepseek-chat",
		label: "DeepSeek Chat",
		provider: "DEEPSEEK",
		contextWindow: "131K",
	},
	{
		value: "deepseek-reasoner",
		label: "DeepSeek Reasoner",
		provider: "DEEPSEEK",
		contextWindow: "131K",
	},
	{
		value: "deepseek-coder",
		label: "DeepSeek Coder",
		provider: "DEEPSEEK",
		contextWindow: "128K",
	},
	{
		value: "deepseek-chat",
		label: "DeepSeek Chat V3",
		provider: "DEEPSEEK",
		contextWindow: "66K",
	},
	{
		value: "deepseek-v3",
		label: "DeepSeek V3",
		provider: "DEEPSEEK",
		contextWindow: "66K",
	},
	{
		value: "deepseek-r1",
		label: "DeepSeek R1",
		provider: "DEEPSEEK",
		contextWindow: "66K",
	},
	{
		value: "deepseek-r1-0528",
		label: "DeepSeek R1 (0528)",
		provider: "DEEPSEEK",
		contextWindow: "65K",
	},

	// xAI (Grok)
	{ value: "grok-4", label: "Grok 4", provider: "XAI", contextWindow: "256K" },
	{ value: "grok-3", label: "Grok 3", provider: "XAI", contextWindow: "131K" },
	{
		value: "grok-3-mini",
		label: "Grok 3 Mini",
		provider: "XAI",
		contextWindow: "131K",
	},
	{
		value: "grok-3-fast-beta",
		label: "Grok 3 Fast",
		provider: "XAI",
		contextWindow: "131K",
	},
	{
		value: "grok-3-mini-fast",
		label: "Grok 3 Mini Fast",
		provider: "XAI",
		contextWindow: "131K",
	},
	{ value: "grok-2", label: "Grok 2", provider: "XAI", contextWindow: "131K" },
	{
		value: "grok-2-vision",
		label: "Grok 2 Vision",
		provider: "XAI",
		contextWindow: "33K",
	},

	// Azure OpenAI
	{
		value: "gpt-4o",
		label: "Azure GPT-4o",
		provider: "AZURE_OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4o-mini",
		label: "Azure GPT-4o Mini",
		provider: "AZURE_OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4o-2024-11-20",
		label: "Azure GPT-4o (Nov 2024)",
		provider: "AZURE_OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4-turbo",
		label: "Azure GPT-4 Turbo",
		provider: "AZURE_OPENAI",
		contextWindow: "128K",
	},
	{
		value: "gpt-4",
		label: "Azure GPT-4",
		provider: "AZURE_OPENAI",
		contextWindow: "8K",
	},
	{
		value: "gpt-35-turbo",
		label: "Azure GPT-3.5 Turbo",
		provider: "AZURE_OPENAI",
		contextWindow: "4K",
	},
	{
		value: "o1",
		label: "Azure O1",
		provider: "AZURE_OPENAI",
		contextWindow: "200K",
	},
	{
		value: "o1-mini",
		label: "Azure O1 Mini",
		provider: "AZURE_OPENAI",
		contextWindow: "128K",
	},
	{
		value: "o3-mini",
		label: "Azure O3 Mini",
		provider: "AZURE_OPENAI",
		contextWindow: "200K",
	},
	{
		value: "gpt-4.1",
		label: "Azure GPT-4.1",
		provider: "AZURE_OPENAI",
		contextWindow: "1M",
	},
	{
		value: "gpt-4.1-mini",
		label: "Azure GPT-4.1 Mini",
		provider: "AZURE_OPENAI",
		contextWindow: "1M",
	},
	{
		value: "gpt-5",
		label: "Azure GPT-5",
		provider: "AZURE_OPENAI",
		contextWindow: "272K",
	},

	// AWS Bedrock
	{
		value: "anthropic.claude-3-5-sonnet-20241022-v2:0",
		label: "Bedrock Claude 3.5 Sonnet",
		provider: "BEDROCK",
		contextWindow: "200K",
	},
	{
		value: "anthropic.claude-3-7-sonnet-20250219-v1:0",
		label: "Bedrock Claude 3.7 Sonnet",
		provider: "BEDROCK",
		contextWindow: "200K",
	},
	{
		value: "anthropic.claude-4-sonnet-20250514-v1:0",
		label: "Bedrock Claude 4 Sonnet",
		provider: "BEDROCK",
		contextWindow: "1M",
	},
	{
		value: "anthropic.claude-3-opus-20240229-v1:0",
		label: "Bedrock Claude 3 Opus",
		provider: "BEDROCK",
		contextWindow: "200K",
	},
	{
		value: "anthropic.claude-3-haiku-20240307-v1:0",
		label: "Bedrock Claude 3 Haiku",
		provider: "BEDROCK",
		contextWindow: "200K",
	},
	{
		value: "anthropic.claude-haiku-4-5-20251001-v1:0",
		label: "Bedrock Claude Haiku 4.5",
		provider: "BEDROCK",
		contextWindow: "200K",
	},
	{
		value: "amazon.nova-pro-v1:0",
		label: "Amazon Nova Pro",
		provider: "BEDROCK",
		contextWindow: "300K",
	},
	{
		value: "amazon.nova-lite-v1:0",
		label: "Amazon Nova Lite",
		provider: "BEDROCK",
		contextWindow: "300K",
	},
	{
		value: "amazon.nova-micro-v1:0",
		label: "Amazon Nova Micro",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "meta.llama3-3-70b-instruct-v1:0",
		label: "Bedrock Llama 3.3 70B",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "meta.llama3-1-405b-instruct-v1:0",
		label: "Bedrock Llama 3.1 405B",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "meta.llama3-1-70b-instruct-v1:0",
		label: "Bedrock Llama 3.1 70B",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "meta.llama3-1-8b-instruct-v1:0",
		label: "Bedrock Llama 3.1 8B",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "meta.llama4-maverick-17b-instruct-v1:0",
		label: "Bedrock Llama 4 Maverick 17B",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "meta.llama4-scout-17b-instruct-v1:0",
		label: "Bedrock Llama 4 Scout 17B",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "mistral.mistral-large-2407-v1:0",
		label: "Bedrock Mistral Large",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "mistral.mixtral-8x7b-instruct-v0:1",
		label: "Bedrock Mixtral 8x7B",
		provider: "BEDROCK",
		contextWindow: "32K",
	},
	{
		value: "cohere.command-r-plus-v1:0",
		label: "Bedrock Cohere Command R+",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "cohere.command-r-v1:0",
		label: "Bedrock Cohere Command R",
		provider: "BEDROCK",
		contextWindow: "128K",
	},
	{
		value: "ai21.jamba-1-5-large-v1:0",
		label: "Bedrock Jamba 1.5 Large",
		provider: "BEDROCK",
		contextWindow: "256K",
	},
	{
		value: "ai21.jamba-1-5-mini-v1:0",
		label: "Bedrock Jamba 1.5 Mini",
		provider: "BEDROCK",
		contextWindow: "256K",
	},
	{
		value: "deepseek.v3-v1:0",
		label: "Bedrock DeepSeek V3",
		provider: "BEDROCK",
		contextWindow: "164K",
	},

	// Vertex AI
	{
		value: "gemini-2.5-flash",
		label: "Vertex Gemini 2.5 Flash",
		provider: "VERTEX_AI",
		contextWindow: "1M",
	},
	{
		value: "gemini-2.5-pro",
		label: "Vertex Gemini 2.5 Pro",
		provider: "VERTEX_AI",
		contextWindow: "1M",
	},
	{
		value: "gemini-2.0-flash",
		label: "Vertex Gemini 2.0 Flash",
		provider: "VERTEX_AI",
		contextWindow: "1M",
	},
	{
		value: "gemini-1.5-flash",
		label: "Vertex Gemini 1.5 Flash",
		provider: "VERTEX_AI",
		contextWindow: "1M",
	},
	{
		value: "gemini-1.5-pro",
		label: "Vertex Gemini 1.5 Pro",
		provider: "VERTEX_AI",
		contextWindow: "2M",
	},
	{
		value: "claude-3-5-sonnet-v2@20241022",
		label: "Vertex Claude 3.5 Sonnet",
		provider: "VERTEX_AI",
		contextWindow: "200K",
	},
	{
		value: "claude-3-7-sonnet@20250219",
		label: "Vertex Claude 3.7 Sonnet",
		provider: "VERTEX_AI",
		contextWindow: "200K",
	},
	{
		value: "claude-sonnet-4@20250514",
		label: "Vertex Claude Sonnet 4",
		provider: "VERTEX_AI",
		contextWindow: "1M",
	},
	{
		value: "claude-3-opus@20240229",
		label: "Vertex Claude 3 Opus",
		provider: "VERTEX_AI",
		contextWindow: "200K",
	},
	{
		value: "claude-3-haiku@20240307",
		label: "Vertex Claude 3 Haiku",
		provider: "VERTEX_AI",
		contextWindow: "200K",
	},
	{
		value: "claude-haiku-4-5@20251001",
		label: "Vertex Claude Haiku 4.5",
		provider: "VERTEX_AI",
		contextWindow: "200K",
	},
	{
		value: "meta/llama-3.1-405b-instruct-maas",
		label: "Vertex Llama 3.1 405B",
		provider: "VERTEX_AI",
		contextWindow: "128K",
	},
	{
		value: "mistral-large@2411-001",
		label: "Vertex Mistral Large",
		provider: "VERTEX_AI",
		contextWindow: "128K",
	},

	// Groq
	{
		value: "llama-3.3-70b-versatile",
		label: "Groq Llama 3.3 70B",
		provider: "GROQ",
		contextWindow: "128K",
	},
	{
		value: "llama-3.3-70b-specdec",
		label: "Groq Llama 3.3 70B Specdec",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "llama-3.1-70b-versatile",
		label: "Groq Llama 3.1 70B",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "llama-3.1-8b-instant",
		label: "Groq Llama 3.1 8B",
		provider: "GROQ",
		contextWindow: "128K",
	},
	{
		value: "llama-3.2-90b-vision-preview",
		label: "Groq Llama 3.2 90B Vision",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "llama-3.2-11b-vision-preview",
		label: "Groq Llama 3.2 11B Vision",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "llama-3.2-3b-preview",
		label: "Groq Llama 3.2 3B",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "llama-3.2-1b-preview",
		label: "Groq Llama 3.2 1B",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "mixtral-8x7b-32768",
		label: "Groq Mixtral 8x7B",
		provider: "GROQ",
		contextWindow: "33K",
	},
	{
		value: "gemma2-9b-it",
		label: "Groq Gemma 2 9B",
		provider: "GROQ",
		contextWindow: "8K",
	},
	{
		value: "deepseek-r1-distill-llama-70b",
		label: "Groq DeepSeek R1 Distill",
		provider: "GROQ",
		contextWindow: "128K",
	},
	{
		value: "meta-llama/llama-4-maverick-17b-128e-instruct",
		label: "Groq Llama 4 Maverick",
		provider: "GROQ",
		contextWindow: "131K",
	},
	{
		value: "meta-llama/llama-4-scout-17b-16e-instruct",
		label: "Groq Llama 4 Scout",
		provider: "GROQ",
		contextWindow: "131K",
	},
	{
		value: "openai/gpt-oss-120b",
		label: "Groq GPT-OSS-120B",
		provider: "GROQ",
		contextWindow: "131K",
	},
	{
		value: "openai/gpt-oss-20b",
		label: "Groq GPT-OSS-20B",
		provider: "GROQ",
		contextWindow: "131K",
	},
	{
		value: "moonshotai/kimi-k2-instruct",
		label: "Groq Kimi K2",
		provider: "GROQ",
		contextWindow: "131K",
	},

	// Cohere
	{
		value: "command-a-03-2025",
		label: "Command A (03-2025)",
		provider: "COHERE",
		contextWindow: "256K",
	},
	{
		value: "command-r-plus",
		label: "Command R+",
		provider: "COHERE",
		contextWindow: "128K",
	},
	{
		value: "command-r",
		label: "Command R",
		provider: "COHERE",
		contextWindow: "128K",
	},
	{
		value: "command-r-plus-08-2024",
		label: "Command R+ (08-2024)",
		provider: "COHERE",
		contextWindow: "128K",
	},
	{
		value: "command-r-08-2024",
		label: "Command R (08-2024)",
		provider: "COHERE",
		contextWindow: "128K",
	},
	{
		value: "command",
		label: "Command",
		provider: "COHERE",
		contextWindow: "4K",
	},

	// Mistral
	{
		value: "mistral-large-latest",
		label: "Mistral Large Latest",
		provider: "MISTRAL",
		contextWindow: "128K",
	},
	{
		value: "mistral-large-2411",
		label: "Mistral Large 2411",
		provider: "MISTRAL",
		contextWindow: "128K",
	},
	{
		value: "mistral-medium-latest",
		label: "Mistral Medium Latest",
		provider: "MISTRAL",
		contextWindow: "131K",
	},
	{
		value: "mistral-medium-2505",
		label: "Mistral Medium 2505",
		provider: "MISTRAL",
		contextWindow: "131K",
	},
	{
		value: "mistral-small-latest",
		label: "Mistral Small Latest",
		provider: "MISTRAL",
		contextWindow: "32K",
	},
	{
		value: "open-mistral-nemo",
		label: "Mistral Nemo",
		provider: "MISTRAL",
		contextWindow: "128K",
	},
	{
		value: "open-mixtral-8x7b",
		label: "Mixtral 8x7B",
		provider: "MISTRAL",
		contextWindow: "32K",
	},
	{
		value: "open-mixtral-8x22b",
		label: "Mixtral 8x22B",
		provider: "MISTRAL",
		contextWindow: "65K",
	},
	{
		value: "codestral-latest",
		label: "Codestral Latest",
		provider: "MISTRAL",
		contextWindow: "32K",
	},
	{
		value: "pixtral-large-latest",
		label: "Pixtral Large Latest",
		provider: "MISTRAL",
		contextWindow: "128K",
	},
	{
		value: "magistral-medium-latest",
		label: "Magistral Medium Latest",
		provider: "MISTRAL",
		contextWindow: "40K",
	},

	// Together AI
	{
		value: "meta-llama/Meta-Llama-3.3-70B-Instruct-Turbo",
		label: "Together Llama 3.3 70B Turbo",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
		label: "Together Llama 3.1 405B Turbo",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
		label: "Together Llama 3.1 70B Turbo",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
		label: "Together Llama 3.1 8B Turbo",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
		label: "Together Llama 4 Maverick",
		provider: "TOGETHER_AI",
		contextWindow: "131K",
	},
	{
		value: "meta-llama/Llama-4-Scout-17B-16E-Instruct",
		label: "Together Llama 4 Scout",
		provider: "TOGETHER_AI",
		contextWindow: "131K",
	},
	{
		value: "deepseek-ai/DeepSeek-V3.1",
		label: "Together DeepSeek V3.1",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "deepseek-ai/DeepSeek-V3",
		label: "Together DeepSeek V3",
		provider: "TOGETHER_AI",
		contextWindow: "66K",
	},
	{
		value: "deepseek-ai/DeepSeek-R1",
		label: "Together DeepSeek R1",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "mistralai/Mixtral-8x7B-Instruct-v0.1",
		label: "Together Mixtral 8x7B",
		provider: "TOGETHER_AI",
		contextWindow: "32K",
	},
	{
		value: "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
		label: "Together Qwen3 Coder 480B",
		provider: "TOGETHER_AI",
		contextWindow: "256K",
	},
	{
		value: "Qwen/Qwen3-235B-A22B-Instruct-2507-tput",
		label: "Together Qwen3 235B",
		provider: "TOGETHER_AI",
		contextWindow: "262K",
	},
	{
		value: "moonshotai/Kimi-K2-Instruct",
		label: "Together Kimi K2",
		provider: "TOGETHER_AI",
		contextWindow: "131K",
	},
	{
		value: "openai/gpt-oss-120b",
		label: "Together GPT-OSS-120B",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},
	{
		value: "openai/gpt-oss-20b",
		label: "Together GPT-OSS-20B",
		provider: "TOGETHER_AI",
		contextWindow: "128K",
	},

	// Fireworks AI
	{
		value: "accounts/fireworks/models/llama-v3p3-70b-instruct",
		label: "Fireworks Llama 3.3 70B",
		provider: "FIREWORKS_AI",
		contextWindow: "131K",
	},
	{
		value: "accounts/fireworks/models/llama-v3p1-405b-instruct",
		label: "Fireworks Llama 3.1 405B",
		provider: "FIREWORKS_AI",
		contextWindow: "128K",
	},
	{
		value: "accounts/fireworks/models/llama4-maverick-instruct-basic",
		label: "Fireworks Llama 4 Maverick",
		provider: "FIREWORKS_AI",
		contextWindow: "131K",
	},
	{
		value: "accounts/fireworks/models/llama4-scout-instruct-basic",
		label: "Fireworks Llama 4 Scout",
		provider: "FIREWORKS_AI",
		contextWindow: "131K",
	},
	{
		value: "accounts/fireworks/models/deepseek-v3p1",
		label: "Fireworks DeepSeek V3.1",
		provider: "FIREWORKS_AI",
		contextWindow: "128K",
	},
	{
		value: "accounts/fireworks/models/deepseek-v3",
		label: "Fireworks DeepSeek V3",
		provider: "FIREWORKS_AI",
		contextWindow: "128K",
	},
	{
		value: "accounts/fireworks/models/deepseek-r1",
		label: "Fireworks DeepSeek R1",
		provider: "FIREWORKS_AI",
		contextWindow: "128K",
	},
	{
		value: "accounts/fireworks/models/mixtral-8x22b-instruct-hf",
		label: "Fireworks Mixtral 8x22B",
		provider: "FIREWORKS_AI",
		contextWindow: "66K",
	},
	{
		value: "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
		label: "Fireworks Qwen2.5 Coder 32B",
		provider: "FIREWORKS_AI",
		contextWindow: "4K",
	},
	{
		value: "accounts/fireworks/models/kimi-k2-instruct",
		label: "Fireworks Kimi K2",
		provider: "FIREWORKS_AI",
		contextWindow: "131K",
	},

	// Replicate
	{
		value: "meta/llama-3-70b-instruct",
		label: "Replicate Llama 3 70B",
		provider: "REPLICATE",
		contextWindow: "8K",
	},
	{
		value: "meta/llama-3-8b-instruct",
		label: "Replicate Llama 3 8B",
		provider: "REPLICATE",
		contextWindow: "8K",
	},
	{
		value: "meta/llama-2-70b-chat",
		label: "Replicate Llama 2 70B",
		provider: "REPLICATE",
		contextWindow: "4K",
	},
	{
		value: "mistralai/mixtral-8x7b-instruct-v0.1",
		label: "Replicate Mixtral 8x7B",
		provider: "REPLICATE",
		contextWindow: "4K",
	},

	// Perplexity
	{
		value: "sonar-pro",
		label: "Sonar Pro",
		provider: "PERPLEXITY",
		contextWindow: "200K",
	},
	{
		value: "sonar",
		label: "Sonar",
		provider: "PERPLEXITY",
		contextWindow: "128K",
	},
	{
		value: "sonar-reasoning-pro",
		label: "Sonar Reasoning Pro",
		provider: "PERPLEXITY",
		contextWindow: "128K",
	},
	{
		value: "sonar-reasoning",
		label: "Sonar Reasoning",
		provider: "PERPLEXITY",
		contextWindow: "128K",
	},
	{
		value: "llama-3.1-sonar-large-128k-online",
		label: "Llama 3.1 Sonar Large Online",
		provider: "PERPLEXITY",
		contextWindow: "127K",
	},
	{
		value: "llama-3.1-sonar-small-128k-online",
		label: "Llama 3.1 Sonar Small Online",
		provider: "PERPLEXITY",
		contextWindow: "127K",
	},

	// OpenRouter
	{
		value: "anthropic/claude-4-opus",
		label: "OpenRouter Claude 4 Opus",
		provider: "OPENROUTER",
		contextWindow: "200K",
	},
	{
		value: "anthropic/claude-sonnet-4",
		label: "OpenRouter Claude Sonnet 4",
		provider: "OPENROUTER",
		contextWindow: "1M",
	},
	{
		value: "anthropic/claude-3.7-sonnet",
		label: "OpenRouter Claude 3.7 Sonnet",
		provider: "OPENROUTER",
		contextWindow: "200K",
	},
	{
		value: "anthropic/claude-3.5-sonnet",
		label: "OpenRouter Claude 3.5 Sonnet",
		provider: "OPENROUTER",
		contextWindow: "200K",
	},
	{
		value: "openai/gpt-5",
		label: "OpenRouter GPT-5",
		provider: "OPENROUTER",
		contextWindow: "272K",
	},
	{
		value: "openai/gpt-4.1",
		label: "OpenRouter GPT-4.1",
		provider: "OPENROUTER",
		contextWindow: "1M",
	},
	{
		value: "openai/gpt-4o",
		label: "OpenRouter GPT-4o",
		provider: "OPENROUTER",
		contextWindow: "128K",
	},
	{
		value: "openai/o3-mini",
		label: "OpenRouter O3 Mini",
		provider: "OPENROUTER",
		contextWindow: "128K",
	},
	{
		value: "x-ai/grok-4",
		label: "OpenRouter Grok 4",
		provider: "OPENROUTER",
		contextWindow: "256K",
	},
	{
		value: "deepseek/deepseek-chat-v3.1",
		label: "OpenRouter DeepSeek Chat V3.1",
		provider: "OPENROUTER",
		contextWindow: "164K",
	},
	{
		value: "deepseek/deepseek-r1",
		label: "OpenRouter DeepSeek R1",
		provider: "OPENROUTER",
		contextWindow: "65K",
	},
	{
		value: "google/gemini-2.5-flash",
		label: "OpenRouter Gemini 2.5 Flash",
		provider: "OPENROUTER",
		contextWindow: "1M",
	},
	{
		value: "google/gemini-2.5-pro",
		label: "OpenRouter Gemini 2.5 Pro",
		provider: "OPENROUTER",
		contextWindow: "1M",
	},

	// Ollama (Local)
	{
		value: "llama3.3",
		label: "Ollama Llama 3.3",
		provider: "OLLAMA",
		contextWindow: "128K",
	},
	{
		value: "llama3.1",
		label: "Ollama Llama 3.1",
		provider: "OLLAMA",
		contextWindow: "8K",
	},
	{
		value: "llama3",
		label: "Ollama Llama 3",
		provider: "OLLAMA",
		contextWindow: "8K",
	},
	{
		value: "llama2",
		label: "Ollama Llama 2",
		provider: "OLLAMA",
		contextWindow: "4K",
	},
	{
		value: "mistral",
		label: "Ollama Mistral",
		provider: "OLLAMA",
		contextWindow: "8K",
	},
	{
		value: "mixtral-8x7B-Instruct-v0.1",
		label: "Ollama Mixtral 8x7B",
		provider: "OLLAMA",
		contextWindow: "33K",
	},
	{
		value: "codellama",
		label: "Ollama CodeLlama",
		provider: "OLLAMA",
		contextWindow: "4K",
	},
	{
		value: "deepseek-coder-v2-instruct",
		label: "Ollama DeepSeek Coder V2",
		provider: "OLLAMA",
		contextWindow: "33K",
	},

	// Alibaba Qwen
	{
		value: "qwen-plus",
		label: "Qwen Plus",
		provider: "ALIBABA_QWEN",
		contextWindow: "129K",
	},
	{
		value: "qwen-turbo",
		label: "Qwen Turbo",
		provider: "ALIBABA_QWEN",
		contextWindow: "129K",
	},
	{
		value: "qwen-max",
		label: "Qwen Max",
		provider: "ALIBABA_QWEN",
		contextWindow: "31K",
	},
	{
		value: "qwen-coder",
		label: "Qwen Coder",
		provider: "ALIBABA_QWEN",
		contextWindow: "1M",
	},
	{
		value: "qwen3-32b",
		label: "Qwen3 32B",
		provider: "ALIBABA_QWEN",
		contextWindow: "131K",
	},
	{
		value: "qwen3-30b-a3b",
		label: "Qwen3 30B-A3B",
		provider: "ALIBABA_QWEN",
		contextWindow: "129K",
	},
	{
		value: "qwen3-coder-plus",
		label: "Qwen3 Coder Plus",
		provider: "ALIBABA_QWEN",
		contextWindow: "998K",
	},
	{
		value: "qwq-plus",
		label: "QwQ Plus",
		provider: "ALIBABA_QWEN",
		contextWindow: "98K",
	},

	// Moonshot (Kimi)
	{
		value: "kimi-latest",
		label: "Kimi Latest",
		provider: "MOONSHOT",
		contextWindow: "131K",
	},
	{
		value: "kimi-k2-thinking",
		label: "Kimi K2 Thinking",
		provider: "MOONSHOT",
		contextWindow: "262K",
	},
	{
		value: "moonshot-v1-128k",
		label: "Moonshot V1 128K",
		provider: "MOONSHOT",
		contextWindow: "131K",
	},
	{
		value: "moonshot-v1-32k",
		label: "Moonshot V1 32K",
		provider: "MOONSHOT",
		contextWindow: "33K",
	},
	{
		value: "moonshot-v1-8k",
		label: "Moonshot V1 8K",
		provider: "MOONSHOT",
		contextWindow: "8K",
	},

	// Zhipu (GLM)
	{
		value: "z-ai/glm-4.6",
		label: "GLM 4.6",
		provider: "ZHIPU",
		contextWindow: "203K",
	},
	{
		value: "z-ai/glm-4.6:exacto",
		label: "GLM 4.6 Exacto",
		provider: "ZHIPU",
		contextWindow: "203K",
	},

	// Anyscale
	{
		value: "meta-llama/Meta-Llama-3-70B-Instruct",
		label: "Anyscale Llama 3 70B",
		provider: "ANYSCALE",
		contextWindow: "8K",
	},
	{
		value: "meta-llama/Meta-Llama-3-8B-Instruct",
		label: "Anyscale Llama 3 8B",
		provider: "ANYSCALE",
		contextWindow: "8K",
	},
	{
		value: "mistralai/Mixtral-8x7B-Instruct-v0.1",
		label: "Anyscale Mixtral 8x7B",
		provider: "ANYSCALE",
		contextWindow: "16K",
	},

	// DeepInfra
	{
		value: "meta-llama/Meta-Llama-3.3-70B-Instruct",
		label: "DeepInfra Llama 3.3 70B",
		provider: "DEEPINFRA",
		contextWindow: "131K",
	},
	{
		value: "meta-llama/Meta-Llama-3.1-405B-Instruct",
		label: "DeepInfra Llama 3.1 405B",
		provider: "DEEPINFRA",
		contextWindow: "33K",
	},
	{
		value: "meta-llama/Meta-Llama-3.1-70B-Instruct",
		label: "DeepInfra Llama 3.1 70B",
		provider: "DEEPINFRA",
		contextWindow: "131K",
	},
	{
		value: "deepseek-ai/DeepSeek-V3",
		label: "DeepInfra DeepSeek V3",
		provider: "DEEPINFRA",
		contextWindow: "164K",
	},
	{
		value: "deepseek-ai/DeepSeek-R1",
		label: "DeepInfra DeepSeek R1",
		provider: "DEEPINFRA",
		contextWindow: "164K",
	},
	{
		value: "Qwen/Qwen2.5-72B-Instruct",
		label: "DeepInfra Qwen 2.5 72B",
		provider: "DEEPINFRA",
		contextWindow: "33K",
	},
	{
		value: "Qwen/Qwen3-235B-A22B",
		label: "DeepInfra Qwen3 235B",
		provider: "DEEPINFRA",
		contextWindow: "131K",
	},
	{
		value: "google/gemini-2.5-flash",
		label: "DeepInfra Gemini 2.5 Flash",
		provider: "DEEPINFRA",
		contextWindow: "1M",
	},
	{
		value: "anthropic/claude-3-7-sonnet-latest",
		label: "DeepInfra Claude 3.7 Sonnet",
		provider: "DEEPINFRA",
		contextWindow: "200K",
	},

	// Cerebras
	{
		value: "llama-3.3-70b",
		label: "Cerebras Llama 3.3 70B",
		provider: "CEREBRAS",
		contextWindow: "128K",
	},
	{
		value: "llama3.1-70b",
		label: "Cerebras Llama 3.1 70B",
		provider: "CEREBRAS",
		contextWindow: "128K",
	},
	{
		value: "llama3.1-8b",
		label: "Cerebras Llama 3.1 8B",
		provider: "CEREBRAS",
		contextWindow: "128K",
	},
	{
		value: "qwen-3-32b",
		label: "Cerebras Qwen 3 32B",
		provider: "CEREBRAS",
		contextWindow: "128K",
	},
	{
		value: "openai/gpt-oss-120b",
		label: "Cerebras GPT-OSS-120B",
		provider: "CEREBRAS",
		contextWindow: "131K",
	},

	// SambaNova
	{
		value: "Meta-Llama-3.3-70B-Instruct",
		label: "SambaNova Llama 3.3 70B",
		provider: "SAMBANOVA",
		contextWindow: "131K",
	},
	{
		value: "Meta-Llama-3.1-405B-Instruct",
		label: "SambaNova Llama 3.1 405B",
		provider: "SAMBANOVA",
		contextWindow: "16K",
	},
	{
		value: "Meta-Llama-3.1-8B-Instruct",
		label: "SambaNova Llama 3.1 8B",
		provider: "SAMBANOVA",
		contextWindow: "16K",
	},
	{
		value: "DeepSeek-R1",
		label: "SambaNova DeepSeek R1",
		provider: "SAMBANOVA",
		contextWindow: "33K",
	},
	{
		value: "DeepSeek-V3-0324",
		label: "SambaNova DeepSeek V3",
		provider: "SAMBANOVA",
		contextWindow: "33K",
	},
	{
		value: "Llama-4-Maverick-17B-128E-Instruct",
		label: "SambaNova Llama 4 Maverick",
		provider: "SAMBANOVA",
		contextWindow: "131K",
	},
	{
		value: "Llama-4-Scout-17B-16E-Instruct",
		label: "SambaNova Llama 4 Scout",
		provider: "SAMBANOVA",
		contextWindow: "8K",
	},
	{
		value: "QwQ-32B",
		label: "SambaNova QwQ 32B",
		provider: "SAMBANOVA",
		contextWindow: "16K",
	},
	{
		value: "Qwen3-32B",
		label: "SambaNova Qwen3 32B",
		provider: "SAMBANOVA",
		contextWindow: "8K",
	},

	// AI21 Labs
	{
		value: "jamba-1.5-large",
		label: "Jamba 1.5 Large",
		provider: "AI21",
		contextWindow: "256K",
	},
	{
		value: "jamba-1.5-mini",
		label: "Jamba 1.5 Mini",
		provider: "AI21",
		contextWindow: "256K",
	},
	{
		value: "jamba-large-1.6",
		label: "Jamba Large 1.6",
		provider: "AI21",
		contextWindow: "256K",
	},
	{
		value: "jamba-mini-1.6",
		label: "Jamba Mini 1.6",
		provider: "AI21",
		contextWindow: "256K",
	},

	// Cloudflare
	{
		value: "@cf/meta/llama-2-7b-chat-fp16",
		label: "Cloudflare Llama 2 7B",
		provider: "CLOUDFLARE",
		contextWindow: "3K",
	},
	{
		value: "@cf/mistral/mistral-7b-instruct-v0.1",
		label: "Cloudflare Mistral 7B",
		provider: "CLOUDFLARE",
		contextWindow: "8K",
	},

	// Databricks
	{
		value: "databricks-meta-llama-3-3-70b-instruct",
		label: "Databricks Llama 3.3 70B",
		provider: "DATABRICKS",
		contextWindow: "128K",
	},
	{
		value: "databricks-meta-llama-3-1-405b-instruct",
		label: "Databricks Llama 3.1 405B",
		provider: "DATABRICKS",
		contextWindow: "128K",
	},
	{
		value: "databricks-claude-3-7-sonnet",
		label: "Databricks Claude 3.7 Sonnet",
		provider: "DATABRICKS",
		contextWindow: "200K",
	},
	{
		value: "databricks-llama-4-maverick",
		label: "Databricks Llama 4 Maverick",
		provider: "DATABRICKS",
		contextWindow: "128K",
	},
];

// Helper function to get models by provider
export function getModelsByProvider(provider: string): LLMModel[] {
	return LLM_MODELS.filter((model) => model.provider === provider);
}

// Helper function to get all providers that have models
export function getProvidersWithModels(): string[] {
	return Array.from(new Set(LLM_MODELS.map((model) => model.provider)));
}
