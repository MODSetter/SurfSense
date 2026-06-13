import { useEffect, useState } from "react";
import { ApiBaseUrlField, ApiKeyField } from "./connect-fields";
import type { ProviderConnectFormProps } from "./provider-metadata";

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
	const isOllama = provider === "ollama_chat";
	const hint = baseUrlHint(provider);
	const canSubmit = !(baseUrlRequired && !baseUrl.trim());

	useEffect(() => {
		onDraftChange({ base_url: baseUrl || null, api_key: apiKey || null, extra: {} }, canSubmit);
	}, [apiKey, baseUrl, canSubmit, onDraftChange]);

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
				label={isOllama ? "API Key (optional)" : "API Key"}
				placeholder={isOllama ? "Optional for Ollama" : "API key"}
			/>
		</div>
	);
}
