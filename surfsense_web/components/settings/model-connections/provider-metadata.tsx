import { getProviderIcon } from "@/lib/provider-icons";

export const PROVIDER_ORDER = [
	"openai",
	"anthropic",
	"vertex_ai",
	"bedrock",
	"azure",
	"openrouter",
	"ollama_chat",
	"lm_studio",
	"openai_compatible",
];

export const PROVIDER_DISPLAY: Record<
	string,
	{ name: string; subtitle: string; iconKey?: string; defaultBaseUrl?: string }
> = {
	anthropic: {
		name: "Claude",
		subtitle: "Anthropic",
		iconKey: "anthropic",
		defaultBaseUrl: "https://api.anthropic.com/v1",
	},
	azure: { name: "Azure OpenAI", subtitle: "Microsoft Azure", iconKey: "azure_openai" },
	bedrock: { name: "Amazon Bedrock", subtitle: "AWS", iconKey: "bedrock" },
	lm_studio: { name: "LM Studio", subtitle: "LM Studio", iconKey: "custom" },
	ollama_chat: { name: "Ollama", subtitle: "Ollama", iconKey: "ollama" },
	openai: {
		name: "GPT",
		subtitle: "OpenAI",
		iconKey: "openai",
		defaultBaseUrl: "https://api.openai.com/v1",
	},
	openai_compatible: {
		name: "OpenAI-Compatible",
		subtitle: "OpenAI-compatible endpoint",
		iconKey: "custom",
	},
	openrouter: {
		name: "OpenRouter",
		subtitle: "OpenRouter",
		iconKey: "openrouter",
		defaultBaseUrl: "https://openrouter.ai/api/v1",
	},
	vertex_ai: { name: "Gemini", subtitle: "Google Cloud Vertex AI", iconKey: "vertex_ai" },
};

export function providerDisplay(provider: string) {
	const fallback = provider
		.split("_")
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");

	return (
		PROVIDER_DISPLAY[provider] ?? {
			name: fallback || provider,
			subtitle: provider,
			iconKey: provider,
		}
	);
}

export function providerIcon(provider: string, className = "size-4") {
	return getProviderIcon(providerDisplay(provider).iconKey ?? provider, { className });
}

export function providerDefaultBaseUrl(provider: string, registryDefault?: string | null) {
	return registryDefault ?? PROVIDER_DISPLAY[provider]?.defaultBaseUrl ?? "";
}

export const AWS_REGION_OPTIONS = [
	"us-east-1",
	"us-east-2",
	"us-west-2",
	"us-gov-east-1",
	"us-gov-west-1",
	"ap-northeast-1",
	"ap-south-1",
	"ap-southeast-1",
	"ap-southeast-2",
	"ap-east-1",
	"ca-central-1",
	"eu-central-1",
	"eu-west-2",
];

export const VERTEX_DEFAULT_LOCATION = "global";

export const BEDROCK_AUTH_IAM = "iam";
export const BEDROCK_AUTH_ACCESS_KEY = "access_key";
export const BEDROCK_AUTH_LONG_TERM_API_KEY = "long_term_api_key";

export const VERTEX_AUTH_SERVICE_ACCOUNT = "service_account_json";
export const VERTEX_AUTH_WORKLOAD_IDENTITY = "workload_identity";

// Mirrors Onyx's Azure "Target URI" parser: the user pastes the full endpoint
// (e.g. https://res.cognitiveservices.azure.com/openai/deployments/<dep>/chat/completions?api-version=<ver>)
// which we split into api base (origin), api version, and deployment name.
export function parseAzureTargetUri(rawUri: string) {
	try {
		const url = new URL(rawUri);
		const deploymentMatch = url.pathname.match(/\/openai\/deployments\/([^/]+)/i);
		return {
			origin: url.origin,
			apiVersion: url.searchParams.get("api-version")?.trim() ?? "",
			deploymentName: deploymentMatch?.[1] ? deploymentMatch[1].toLowerCase() : "",
			isResponsesPath: /\/openai\/responses/i.test(url.pathname),
		};
	} catch {
		return null;
	}
}

export function isValidAzureTargetUri(rawUri: string) {
	const parsed = parseAzureTargetUri(rawUri);
	if (!parsed) return false;
	return Boolean(parsed.apiVersion) && (Boolean(parsed.deploymentName) || parsed.isResponsesPath);
}

/** Connection payload produced by a provider connect form. */
export interface ConnectionDraft {
	base_url: string | null;
	api_key: string | null;
	extra: Record<string, unknown>;
	/** Model id to seed after creation (providers without discovery, e.g. Azure). */
	seedModelId?: string;
}

/** Props shared by every provider-specific connect form. */
export interface ProviderConnectFormProps {
	provider: string;
	defaultBaseUrl: string;
	baseUrlRequired: boolean;
	onDraftChange: (draft: ConnectionDraft, canSubmit: boolean) => void;
}
