import {
	Bot,
	Cloud,
	Cpu,
	Database,
	Globe,
	Layers,
	Server,
	Settings2,
	Shuffle,
	Sparkles,
	Wand2,
	Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Returns a Lucide icon element for the given LLM / image-gen provider.
 * Accepts an optional `className` override for the icon size.
 */
export function getProviderIcon(
	provider: string,
	{
		isAutoMode,
		className = "size-4",
	}: { isAutoMode?: boolean; className?: string } = {}
) {
	if (isAutoMode || provider?.toUpperCase() === "AUTO") {
		return <Shuffle className={cn(className, "text-violet-500")} />;
	}

	switch (provider?.toUpperCase()) {
		case "OPENAI":
			return <Sparkles className={cn(className, "text-emerald-500")} />;
		case "ANTHROPIC":
			return <Bot className={cn(className, "text-amber-600")} />;
		case "GOOGLE":
			return <Cloud className={cn(className, "text-blue-500")} />;
		case "AZURE_OPENAI":
			return <Sparkles className={cn(className, "text-sky-500")} />;
		case "GROQ":
			return <Zap className={cn(className, "text-orange-500")} />;
		case "OLLAMA":
			return <Settings2 className={cn(className, "text-gray-500")} />;
		case "XAI":
			return <Bot className={cn(className, "text-violet-500")} />;
		case "MISTRAL":
			return <Wand2 className={cn(className, "text-orange-400")} />;
		case "DEEPSEEK":
			return <Layers className={cn(className, "text-blue-400")} />;
		case "COHERE":
			return <Globe className={cn(className, "text-rose-500")} />;
		case "BEDROCK":
			return <Server className={cn(className, "text-amber-500")} />;
		case "VERTEX_AI":
			return <Cloud className={cn(className, "text-red-400")} />;
		case "OPENROUTER":
			return <Globe className={cn(className, "text-indigo-500")} />;
		case "TOGETHER_AI":
			return <Cpu className={cn(className, "text-teal-500")} />;
		case "FIREWORKS_AI":
			return <Zap className={cn(className, "text-red-500")} />;
		case "PERPLEXITY":
			return <Sparkles className={cn(className, "text-cyan-500")} />;
		case "CEREBRAS":
			return <Cpu className={cn(className, "text-purple-500")} />;
		case "RECRAFT":
			return <Wand2 className={cn(className, "text-teal-500")} />;
		case "REPLICATE":
			return <Database className={cn(className, "text-blue-500")} />;
		case "ALIBABA_QWEN":
			return <Bot className={cn(className, "text-orange-500")} />;
		case "MOONSHOT":
			return <Bot className={cn(className, "text-indigo-400")} />;
		case "ZHIPU":
			return <Bot className={cn(className, "text-green-500")} />;
		case "ANYSCALE":
			return <Bot className={cn(className, "text-sky-400")} />;
		case "DEEPINFRA":
			return <Bot className={cn(className, "text-pink-500")} />;
		case "SAMBANOVA":
			return <Bot className={cn(className, "text-lime-500")} />;
		case "AI21":
			return <Bot className={cn(className, "text-blue-600")} />;
		case "CLOUDFLARE":
			return <Bot className={cn(className, "text-orange-400")} />;
		case "DATABRICKS":
			return <Bot className={cn(className, "text-red-600")} />;
		case "COMETAPI":
			return <Bot className={cn(className, "text-yellow-500")} />;
		case "HUGGINGFACE":
			return <Bot className={cn(className, "text-yellow-400")} />;
		case "CUSTOM":
			return <Bot className={cn(className, "text-gray-400")} />;
		case "XINFERENCE":
			return <Bot className={cn(className, "text-teal-400")} />;
		case "NSCALE":
			return <Bot className={cn(className, "text-cyan-400")} />;
		default:
			return <Bot className={cn(className, "text-muted-foreground")} />;
	}
}

