import { Bot, Shuffle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Ai21Icon } from "@/components/icons/providers";
import { AnthropicIcon } from "@/components/icons/providers";
import { AnyscaleIcon } from "@/components/icons/providers";
import { BedrockIcon } from "@/components/icons/providers";
import { CerebrasIcon } from "@/components/icons/providers";
import { CloudflareIcon } from "@/components/icons/providers";
import { CohereIcon } from "@/components/icons/providers";
import { CometApiIcon } from "@/components/icons/providers";
import { DatabricksIcon } from "@/components/icons/providers";
import { DeepInfraIcon } from "@/components/icons/providers";
import { DeepSeekIcon } from "@/components/icons/providers";
import { FireworksAiIcon } from "@/components/icons/providers";
import { GeminiIcon } from "@/components/icons/providers";
import { GroqIcon } from "@/components/icons/providers";
import { HuggingFaceIcon } from "@/components/icons/providers";
import { MistralIcon } from "@/components/icons/providers";
import { MoonshotIcon } from "@/components/icons/providers";
import { NscaleIcon } from "@/components/icons/providers";
import { OllamaIcon } from "@/components/icons/providers";
import { OpenaiIcon } from "@/components/icons/providers";
import { OpenRouterIcon } from "@/components/icons/providers";
import { PerplexityIcon } from "@/components/icons/providers";
import { QwenIcon } from "@/components/icons/providers";
import { RecraftIcon } from "@/components/icons/providers";
import { ReplicateIcon } from "@/components/icons/providers";
import { SambaNovaIcon } from "@/components/icons/providers";
import { TogetherAiIcon } from "@/components/icons/providers";
import { VertexAiIcon } from "@/components/icons/providers";
import { XaiIcon } from "@/components/icons/providers";
import { XinferenceIcon } from "@/components/icons/providers";
import { ZhipuIcon } from "@/components/icons/providers";

/**
 * Returns a Lucide icon element for the given LLM / image-gen provider.
 * Accepts an optional `className` override for the icon size.
 */
export function getProviderIcon(
	provider: string,
	{ isAutoMode, className = "size-4" }: { isAutoMode?: boolean; className?: string } = {}
) {
	if (isAutoMode || provider?.toUpperCase() === "AUTO") {
		return <Shuffle className={cn(className, "text-violet-800")} />;
	}

	switch (provider?.toUpperCase()) {
		case "AI21":
			return <Ai21Icon className={cn(className)} />;
		case "ALIBABA_QWEN":
			return <QwenIcon className={cn(className)} />;
		case "ANTHROPIC":
			return <AnthropicIcon className={cn(className)} />;
		case "ANYSCALE":
			return <AnyscaleIcon className={cn(className)} />;
		case "AZURE":
		case "AZURE_OPENAI":
			return <OpenaiIcon className={cn(className)} />;
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
			return <Bot className={cn(className, "text-gray-400")} />;
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
		case "GROQ":
			return <GroqIcon className={cn(className)} />;
		case "HUGGINGFACE":
			return <HuggingFaceIcon className={cn(className)} />;
		case "MISTRAL":
			return <MistralIcon className={cn(className)} />;
		case "MOONSHOT":
			return <MoonshotIcon className={cn(className)} />;
		case "NSCALE":
			return <NscaleIcon className={cn(className)} />;
		case "OLLAMA":
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
			return <Bot className={cn(className, "text-muted-foreground")} />;
	}
}
