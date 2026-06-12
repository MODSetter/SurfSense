import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ConnectFormFooter } from "./connect-fields";
import {
	AWS_REGION_OPTIONS,
	BEDROCK_AUTH_ACCESS_KEY,
	BEDROCK_AUTH_IAM,
	BEDROCK_AUTH_LONG_TERM_API_KEY,
	type ProviderConnectFormProps,
} from "./provider-metadata";

/**
 * Amazon Bedrock connect form. Region + auth method drive which AWS credentials
 * are collected; everything rides along in `extra.litellm_params`.
 */
export function BedrockConnectForm({ isPending, onCancel, onSubmit }: ProviderConnectFormProps) {
	const [region, setRegion] = useState("");
	const [authMethod, setAuthMethod] = useState(BEDROCK_AUTH_ACCESS_KEY);
	const [accessKeyId, setAccessKeyId] = useState("");
	const [secretAccessKey, setSecretAccessKey] = useState("");
	const [bearerToken, setBearerToken] = useState("");

	const canSubmit = (() => {
		if (!region) return false;
		if (authMethod === BEDROCK_AUTH_ACCESS_KEY) {
			return Boolean(accessKeyId && secretAccessKey);
		}
		if (authMethod === BEDROCK_AUTH_LONG_TERM_API_KEY) {
			return Boolean(bearerToken);
		}
		return true;
	})();

	function handleSubmit() {
		const params: Record<string, string> = { aws_region_name: region };
		if (authMethod === BEDROCK_AUTH_ACCESS_KEY) {
			params.aws_access_key_id = accessKeyId;
			params.aws_secret_access_key = secretAccessKey;
		} else if (authMethod === BEDROCK_AUTH_LONG_TERM_API_KEY) {
			params.aws_bearer_token_bedrock = bearerToken;
		}
		onSubmit({ base_url: null, api_key: null, extra: { litellm_params: params } });
	}

	return (
		<>
			<div className="flex flex-col gap-4">
				<div className="flex flex-col gap-2">
					<Label>AWS Region</Label>
					<Select value={region || undefined} onValueChange={setRegion}>
						<SelectTrigger>
							<SelectValue placeholder="Select a region" />
						</SelectTrigger>
						<SelectContent>
							{AWS_REGION_OPTIONS.map((option) => (
								<SelectItem key={option} value={option}>
									{option}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex flex-col gap-2">
					<Label>Authentication Method</Label>
					<Select value={authMethod} onValueChange={setAuthMethod}>
						<SelectTrigger>
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value={BEDROCK_AUTH_IAM}>Environment IAM Role</SelectItem>
							<SelectItem value={BEDROCK_AUTH_ACCESS_KEY}>Access Key</SelectItem>
							<SelectItem value={BEDROCK_AUTH_LONG_TERM_API_KEY}>Long-term API Key</SelectItem>
						</SelectContent>
					</Select>
				</div>
				{authMethod === BEDROCK_AUTH_ACCESS_KEY ? (
					<>
						<div className="flex flex-col gap-2">
							<Label>AWS Access Key ID</Label>
							<Input
								value={accessKeyId}
								onChange={(event) => setAccessKeyId(event.target.value)}
								placeholder="AKIAIOSFODNN7EXAMPLE"
							/>
						</div>
						<div className="flex flex-col gap-2">
							<Label>AWS Secret Access Key</Label>
							<Input
								value={secretAccessKey}
								onChange={(event) => setSecretAccessKey(event.target.value)}
								placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
								type="password"
							/>
						</div>
					</>
				) : null}
				{authMethod === BEDROCK_AUTH_LONG_TERM_API_KEY ? (
					<div className="flex flex-col gap-2">
						<Label>Long-term API Key</Label>
						<Input
							value={bearerToken}
							onChange={(event) => setBearerToken(event.target.value)}
							placeholder="Your long-term API key"
							type="password"
						/>
					</div>
				) : null}
				{authMethod === BEDROCK_AUTH_IAM ? (
					<p className="text-xs text-muted-foreground">
						SurfSense will use the IAM role attached to the environment it&apos;s running in to
						authenticate.
					</p>
				) : null}
				<p className="text-xs text-muted-foreground">
					Add Bedrock model IDs from the provider&apos;s settings after connecting.
				</p>
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
