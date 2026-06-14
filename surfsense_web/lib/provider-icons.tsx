import { Cpu, Shuffle } from "lucide-react";
import {
	Ai21Icon,
	AnyscaleIcon,
	AzureIcon,
	BedrockIcon,
	CerebrasIcon,
	ClaudeIcon,
	CloudflareIcon,
	CohereIcon,
	CometApiIcon,
	DatabricksIcon,
	DeepInfraIcon,
	DeepSeekIcon,
	FireworksAiIcon,
	GeminiIcon,
	GitHubModelsIcon,
	GroqIcon,
	HuggingFaceIcon,
	LmStudioIcon,
	MiniMaxIcon,
	MistralIcon,
	MoonshotIcon,
	NscaleIcon,
	OllamaIcon,
	OpenaiIcon,
	OpenRouterIcon,
	PerplexityIcon,
	QwenIcon,
	RecraftIcon,
	ReplicateIcon,
	SambaNovaIcon,
	TogetherAiIcon,
	VertexAiIcon,
	XaiIcon,
	XinferenceIcon,
	ZhipuIcon,
} from "@/components/icons/providers";
import { cn } from "@/lib/utils";

export const AUTO_PROVIDER_ICON_KEY = "AUTO";

/**
 * Returns a Lucide icon element for the given LLM / image-gen provider.
 * Accepts an optional `className` override for the icon size.
 */
export function getProviderIcon(
	provider: string,
	{ isAutoMode, className = "size-4" }: { isAutoMode?: boolean; className?: string } = {}
) {
	if (isAutoMode || provider?.toUpperCase() === AUTO_PROVIDER_ICON_KEY) {
		return <Shuffle className={cn(className, "text-muted-foreground")} />;
	}

	switch (provider?.toUpperCase()) {
		case "AI21":
			return <Ai21Icon className={cn(className)} />;
		case "ALIBABA_QWEN":
			return <QwenIcon className={cn(className)} />;
		case "ANTHROPIC":
		case "CLAUDE":
			return <ClaudeIcon className={cn(className)} />;
		case "ANYSCALE":
			return <AnyscaleIcon className={cn(className)} />;
		case "AZURE":
		case "AZURE_OPENAI":
			return <AzureIcon className={cn(className)} />;
		case "AWS_BEDROCK":
		case "BEDROCK":
			return <BedrockIcon className={cn(className)} />;
		case "CEREBRAS":
			return <CerebrasIcon className={cn(className)} />;
		case "CLOUDFLARE":
			return <CloudflareIcon className={cn(className)} />;
		case "COHERE":
			return <CohereIcon className={cn(className)} />;
		case "COMETAPI":
			return <CometApiIcon className={cn(className)} />;
		case "CUSTOM":
			return <Cpu className={cn(className)} />;
		case "DATABRICKS":
			return <DatabricksIcon className={cn(className)} />;
		case "DEEPINFRA":
			return <DeepInfraIcon className={cn(className)} />;
		case "DEEPSEEK":
			return <DeepSeekIcon className={cn(className)} />;
		case "FIREWORKS_AI":
			return <FireworksAiIcon className={cn(className)} />;
		case "GOOGLE":
			return <GeminiIcon className={cn(className)} />;
		case "GITHUB_MODELS":
			return <GitHubModelsIcon className={cn(className)} />;
		case "GROQ":
			return <GroqIcon className={cn(className)} />;
		case "HUGGINGFACE":
			return <HuggingFaceIcon className={cn(className)} />;
		case "LM_STUDIO":
			return <LmStudioIcon className={cn(className)} />;
		case "MINIMAX":
			return <MiniMaxIcon className={cn(className)} />;
		case "MISTRAL":
			return <MistralIcon className={cn(className)} />;
		case "MOONSHOT":
			return <MoonshotIcon className={cn(className)} />;
		case "NSCALE":
			return <NscaleIcon className={cn(className)} />;
		case "OLLAMA":
		case "OLLAMA_CHAT":
			return <OllamaIcon className={cn(className)} />;
		case "OPENAI":
			return <OpenaiIcon className={cn(className)} />;
		case "OPENROUTER":
			return <OpenRouterIcon className={cn(className)} />;
		case "PERPLEXITY":
			return <PerplexityIcon className={cn(className)} />;
		case "RECRAFT":
			return <RecraftIcon className={cn(className)} />;
		case "REPLICATE":
			return <ReplicateIcon className={cn(className)} />;
		case "SAMBANOVA":
			return <SambaNovaIcon className={cn(className)} />;
		case "TOGETHER_AI":
			return <TogetherAiIcon className={cn(className)} />;
		case "VERTEX_AI":
			return <VertexAiIcon className={cn(className)} />;
		case "XAI":
			return <XaiIcon className={cn(className)} />;
		case "XINFERENCE":
			return <XinferenceIcon className={cn(className)} />;
		case "ZHIPU":
			return <ZhipuIcon className={cn(className)} />;
		default:
			return <Cpu className={cn(className, "text-muted-foreground")} />;
	}
}
