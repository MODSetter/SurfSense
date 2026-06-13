import { useEffect, useState } from "react";
import { ApiBaseUrlField, ApiKeyField } from "./connect-fields";
import type { ProviderConnectFormProps } from "./provider-metadata";

const OPTIONAL_API_KEY_PROVIDERS = new Set(["ollama_chat", "lm_studio", "openai_compatible"]);

function baseUrlHint(provider: string) {
	if (provider === "ollama_chat" || provider === "lm_studio") {
		return "For local servers, use host.docker.internal instead of localhost.";
	}
	if (provider === "openai_compatible") {
		return "Enter the full endpoint URL.";
	}
	if (provider === "openai" || provider === "anthropic" || provider === "openrouter") {
		return "Override only if you route through a proxy or gateway.";
	}
	return undefined;
}

/**
 * Connect form for OpenAI-compatible / native key providers (OpenAI, Anthropic,
 * OpenRouter, OpenAI-Compatible, LM Studio, Ollama, …). The base URL is
 * prefilled from the provider default.
 */
export function DefaultConnectForm({
	provider,
	defaultBaseUrl,
	baseUrlRequired,
	onDraftChange,
}: ProviderConnectFormProps) {
	const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
	const [apiKey, setApiKey] = useState("");
	const isApiKeyOptional = OPTIONAL_API_KEY_PROVIDERS.has(provider);
	const hint = baseUrlHint(provider);
	const apiKeyValue = apiKey.trim();
	const canSubmit = !(baseUrlRequired && !baseUrl.trim()) && (isApiKeyOptional || Boolean(apiKeyValue));

	useEffect(() => {
		onDraftChange({ base_url: baseUrl || null, api_key: apiKeyValue || null, extra: {} }, canSubmit);
	}, [apiKeyValue, baseUrl, canSubmit, onDraftChange]);

	return (
		<div className="flex flex-col gap-4">
			<ApiBaseUrlField
				value={baseUrl}
				onChange={setBaseUrl}
				placeholder={defaultBaseUrl}
				hint={hint}
			/>
			<ApiKeyField
				value={apiKey}
				onChange={setApiKey}
				label={isApiKeyOptional ? "API Key (optional)" : "API Key"}
				placeholder="Enter your API key"
			/>
		</div>
	);
}
