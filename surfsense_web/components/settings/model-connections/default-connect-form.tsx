import { useState } from "react";
import { ApiBaseUrlField, ApiKeyField, ConnectFormFooter } from "./connect-fields";
import type { ProviderConnectFormProps } from "./provider-metadata";

/**
 * Connect form for OpenAI-compatible / native key providers (OpenAI, Anthropic,
 * OpenRouter, OpenAI-Compatible, LM Studio, Ollama, …). The base URL is
 * prefilled from the provider default.
 */
export function DefaultConnectForm({
	provider,
	defaultBaseUrl,
	baseUrlRequired,
	isPending,
	onCancel,
	onSubmit,
}: ProviderConnectFormProps) {
	const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
	const [apiKey, setApiKey] = useState("");
	const isOllama = provider === "ollama_chat";
	const canSubmit = !(baseUrlRequired && !baseUrl.trim());

	function handleSubmit() {
		onSubmit({ base_url: baseUrl || null, api_key: apiKey || null, extra: {} });
	}

	return (
		<>
			<div className="flex flex-col gap-4">
				<ApiBaseUrlField
					value={baseUrl}
					onChange={setBaseUrl}
					optional={!baseUrlRequired}
					placeholder={defaultBaseUrl}
				/>
				<ApiKeyField
					value={apiKey}
					onChange={setApiKey}
					label={isOllama ? "API Key (optional)" : "API Key"}
					placeholder={isOllama ? "Optional for Ollama" : "API key"}
				/>
			</div>
			<ConnectFormFooter
				onCancel={onCancel}
				onSubmit={handleSubmit}
				canSubmit={canSubmit}
				isPending={isPending}
			/>
		</>
	);
}
