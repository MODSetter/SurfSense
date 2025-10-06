export interface LLMProvider {
	value: string;
	label: string;
	example: string;
	description: string;
}

export const LLM_PROVIDERS: LLMProvider[] = [
	{
		value: "OPENAI",
		label: "OpenAI",
		example: "gpt-4o, gpt-4, gpt-3.5-turbo",
		description: "Industry-leading GPT models with broad capabilities",
	},
	{
		value: "ANTHROPIC",
		label: "Anthropic",
		example: "claude-3-5-sonnet-20241022, claude-3-opus-20240229",
		description: "Claude models with strong reasoning and long context windows",
	},
	{
		value: "GROQ",
		label: "Groq",
		example: "llama3-70b-8192, mixtral-8x7b-32768",
		description: "Lightning-fast inference with custom LPU hardware",
	},
	{
		value: "COHERE",
		label: "Cohere",
		example: "command-r-plus, command-r",
		description: "Enterprise NLP models optimized for business applications",
	},
	{
		value: "HUGGINGFACE",
		label: "HuggingFace",
		example: "microsoft/DialoGPT-medium",
		description: "Access thousands of open-source models",
	},
	{
		value: "AZURE_OPENAI",
		label: "Azure OpenAI",
		example: "gpt-4, gpt-35-turbo",
		description: "OpenAI models with Microsoft Azure enterprise features",
	},
	{
		value: "GOOGLE",
		label: "Google",
		example: "gemini-pro, gemini-pro-vision",
		description: "Gemini models with multimodal capabilities",
	},
	{
		value: "AWS_BEDROCK",
		label: "AWS Bedrock",
		example: "anthropic.claude-v2",
		description: "Fully managed foundation models on AWS infrastructure",
	},
	{
		value: "OLLAMA",
		label: "Ollama",
		example: "llama2, codellama",
		description: "Run open-source models locally on your machine",
	},
	{
		value: "MISTRAL",
		label: "Mistral",
		example: "mistral-large-latest, mistral-medium",
		description: "High-performance open-source models from Europe",
	},
	{
		value: "TOGETHER_AI",
		label: "Together AI",
		example: "togethercomputer/llama-2-70b-chat",
		description: "Scalable cloud platform for open-source models",
	},
	{
		value: "REPLICATE",
		label: "Replicate",
		example: "meta/llama-2-70b-chat",
		description: "Cloud API for running machine learning models",
	},
	{
		value: "OPENROUTER",
		label: "OpenRouter",
		example: "anthropic/claude-opus-4.1, openai/gpt-5",
		description: "Unified API gateway for multiple LLM providers",
	},
	{
		value: "COMETAPI",
		label: "CometAPI",
		example: "gpt-5-mini, claude-sonnet-4-5",
		description: "Access 500+ AI models through one unified API",
	},
	{
		value: "CUSTOM",
		label: "Custom Provider",
		example: "your-custom-model",
		description: "Connect to your own custom model endpoint",
	},
];
