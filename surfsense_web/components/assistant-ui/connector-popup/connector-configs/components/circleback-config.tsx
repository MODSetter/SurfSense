"use client";

import { Check, Copy, Info, Webhook } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { z } from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authenticatedFetch } from "@/lib/auth-utils";
import type { ConnectorConfigProps } from "../index";

export interface CirclebackConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

// Type-safe schema for webhook info response
const circlebackWebhookInfoSchema = z.object({
	webhook_url: z.string(),
	search_space_id: z.number(),
	method: z.string(),
	content_type: z.string(),
	description: z.string(),
	note: z.string(),
});

export type CirclebackWebhookInfo = z.infer<typeof circlebackWebhookInfoSchema>;

export const CirclebackConfig: FC<CirclebackConfigProps> = ({ connector, onNameChange }) => {
	const [name, setName] = useState<string>(connector.name || "");
	const [webhookUrl, setWebhookUrl] = useState<string>("");
	const [webhookInfo, setWebhookInfo] = useState<CirclebackWebhookInfo | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [copied, setCopied] = useState(false);

	// Update name when connector changes
	useEffect(() => {
		setName(connector.name || "");
	}, [connector.name]);

	// Fetch webhook info
	useEffect(() => {
		const fetchWebhookInfo = async () => {
			if (!connector.search_space_id) return;

			const baseUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL;
			if (!baseUrl) {
				console.error("NEXT_PUBLIC_FASTAPI_BACKEND_URL is not configured");
				setIsLoading(false);
				return;
			}

			setIsLoading(true);
			try {
				const response = await authenticatedFetch(
					`${baseUrl}/api/v1/webhooks/circleback/${connector.search_space_id}/info`
				);
				if (response.ok) {
					const data: unknown = await response.json();
					// Runtime validation with zod schema
					const validatedData = circlebackWebhookInfoSchema.parse(data);
					setWebhookInfo(validatedData);
					setWebhookUrl(validatedData.webhook_url);
				}
			} catch (error) {
				console.error("Failed to fetch webhook info:", error);
				// Reset state on error
				setWebhookInfo(null);
				setWebhookUrl("");
			} finally {
				setIsLoading(false);
			}
		};

		fetchWebhookInfo();
	}, [connector.search_space_id]);

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	const handleCopyWebhookUrl = async () => {
		if (webhookUrl) {
			await navigator.clipboard.writeText(webhookUrl);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}
	};

	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="My Circleback Connector"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this connector.
					</p>
				</div>
			</div>

			{/* Webhook Configuration */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
						<Webhook className="h-4 w-4" />
						Webhook Configuration
					</h3>
				</div>

				{isLoading ? (
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Loading webhook information...
					</p>
				) : webhookUrl ? (
					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Webhook URL</Label>
						<div className="flex gap-2">
							<Input
								value={webhookUrl}
								readOnly
								disabled
								className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono text-xs bg-muted/50 cursor-default select-all"
							/>
							<Button
								type="button"
								variant="secondary"
								size="sm"
								onClick={handleCopyWebhookUrl}
								className="shrink-0"
							>
								{copied ? (
									<>
										<Check className="h-4 w-4 mr-2" />
										Copied!
									</>
								) : (
									<>
										<Copy className="h-4 w-4 mr-2" />
										Copy
									</>
								)}
							</Button>
						</div>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Use this URL in your Circleback automation settings to send meeting data to SurfSense.
						</p>
					</div>
				) : (
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Unable to load webhook URL. Please try refreshing the page.
					</p>
				)}

				{webhookInfo && (
					<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
						<Info className="h-3 w-3 sm:h-4 sm:w-4" />
						<AlertTitle className="text-xs sm:text-sm">Configuration Instructions</AlertTitle>
						<AlertDescription className="text-[10px] sm:text-xs !pl-0 mt-1">
							Configure this URL in Circleback Settings → Automations → Create automation → Send
							webhook request. The webhook will automatically send meeting notes, transcripts, and
							action items to this search space.
						</AlertDescription>
					</Alert>
				)}
			</div>
		</div>
	);
};
