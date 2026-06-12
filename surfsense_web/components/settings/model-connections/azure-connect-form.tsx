import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiKeyField, ConnectFormFooter } from "./connect-fields";
import {
	isValidAzureTargetUri,
	type ProviderConnectFormProps,
	parseAzureTargetUri,
} from "./provider-metadata";

/**
 * Azure OpenAI connect form. The user pastes a single Target URI, which we parse
 * into api base, api version, and the deployment name (seeded as the model).
 */
export function AzureConnectForm({ isPending, onCancel, onSubmit }: ProviderConnectFormProps) {
	const [targetUri, setTargetUri] = useState("");
	const [apiKey, setApiKey] = useState("");
	const canSubmit = isValidAzureTargetUri(targetUri) && Boolean(apiKey.trim());

	function handleSubmit() {
		const parsed = parseAzureTargetUri(targetUri);
		onSubmit({
			base_url: parsed?.origin ?? null,
			api_key: apiKey || null,
			extra: parsed?.apiVersion ? { api_version: parsed.apiVersion } : {},
			seedModelId: parsed?.deploymentName || undefined,
		});
	}

	return (
		<>
			<div className="flex flex-col gap-4">
				<div className="flex flex-col gap-2">
					<Label>Target URI</Label>
					<Input
						value={targetUri}
						onChange={(event) => setTargetUri(event.target.value)}
						placeholder="https://your-resource.cognitiveservices.azure.com/openai/deployments/deployment-name/chat/completions?api-version=2025-01-01-preview"
					/>
					<p className="text-xs text-muted-foreground">
						Paste your endpoint target URI from Azure OpenAI (including API base, deployment name,
						and API version).
					</p>
				</div>
				<ApiKeyField
					value={apiKey}
					onChange={setApiKey}
					placeholder="Paste your API key from Azure"
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
