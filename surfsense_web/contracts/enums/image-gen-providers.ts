export interface ImageGenProvider {
	value: string;
	label: string;
	example: string;
	description: string;
	apiBase?: string;
}

/**
 * Image generation providers supported by LiteLLM.
 * See: https://docs.litellm.ai/docs/image_generation#supported-providers
 */
export const IMAGE_GEN_PROVIDERS: ImageGenProvider[] = [
	{
		value: "OPENAI",
		label: "OpenAI",
		example: "dall-e-3, gpt-image-1, dall-e-2",
		description: "DALL-E and GPT Image models",
	},
	{
		value: "AZURE_OPENAI",
		label: "Azure OpenAI",
		example: "azure/dall-e-3, azure/gpt-image-1",
		description: "OpenAI image models on Azure",
	},
	{
		value: "GOOGLE",
		label: "Google AI Studio",
		example: "gemini/imagen-3.0-generate-002",
		description: "Google AI Studio image generation",
	},
	{
		value: "VERTEX_AI",
		label: "Google Vertex AI",
		example: "vertex_ai/imagegeneration@006",
		description: "Vertex AI image generation models",
	},
	{
		value: "BEDROCK",
		label: "AWS Bedrock",
		example: "bedrock/stability.stable-diffusion-xl-v0",
		description: "Stable Diffusion on AWS Bedrock",
	},
	{
		value: "RECRAFT",
		label: "Recraft",
		example: "recraft/recraftv3",
		description: "AI-powered design and image generation",
	},
	{
		value: "OPENROUTER",
		label: "OpenRouter",
		example: "openrouter/google/gemini-2.5-flash-image",
		description: "Image generation via OpenRouter",
	},
	{
		value: "XINFERENCE",
		label: "Xinference",
		example: "xinference/stable-diffusion-xl",
		description: "Self-hosted Stable Diffusion models",
	},
	{
		value: "NSCALE",
		label: "Nscale",
		example: "nscale/flux.1-schnell",
		description: "Nscale image generation",
	},
];

/**
 * Image generation models organized by provider.
 */
export interface ImageGenModel {
	value: string;
	label: string;
	provider: string;
}

export const IMAGE_GEN_MODELS: ImageGenModel[] = [
	// OpenAI
	{ value: "gpt-image-1", label: "GPT Image 1", provider: "OPENAI" },
	{ value: "dall-e-3", label: "DALL-E 3", provider: "OPENAI" },
	{ value: "dall-e-2", label: "DALL-E 2", provider: "OPENAI" },
	// Azure OpenAI
	{ value: "azure/dall-e-3", label: "DALL-E 3 (Azure)", provider: "AZURE_OPENAI" },
	{ value: "azure/gpt-image-1", label: "GPT Image 1 (Azure)", provider: "AZURE_OPENAI" },
	// Recraft
	{ value: "recraft/recraftv3", label: "Recraft V3", provider: "RECRAFT" },
	// Bedrock
	{
		value: "bedrock/stability.stable-diffusion-xl-v0",
		label: "Stable Diffusion XL",
		provider: "BEDROCK",
	},
	// Vertex AI
	{
		value: "vertex_ai/imagegeneration@006",
		label: "Imagen 3",
		provider: "VERTEX_AI",
	},
];

export function getImageGenModelsByProvider(provider: string): ImageGenModel[] {
	return IMAGE_GEN_MODELS.filter((m) => m.provider === provider);
}
