"use client";

import { Info } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ConnectorConfigProps } from "../index";

export const WebcrawlerConfig: FC<ConnectorConfigProps> = ({ connector, onConfigChange }) => {
	// Initialize with existing config values
	const existingApiKey = (connector.config?.FIRECRAWL_API_KEY as string | undefined) || "";
	const existingUrls = (connector.config?.INITIAL_URLS as string | undefined) || "";

	const [apiKey, setApiKey] = useState(existingApiKey);
	const [initialUrls, setInitialUrls] = useState(existingUrls);
	const [showApiKey, setShowApiKey] = useState(false);

	const handleApiKeyChange = (value: string) => {
		setApiKey(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				FIRECRAWL_API_KEY: value.trim() || undefined,
			});
		}
	};

	const handleUrlsChange = (value: string) => {
		setInitialUrls(value);
		if (onConfigChange) {
			// Preserve newlines for multi-line URL input
			// Backend will handle trimming individual URLs when splitting by newline
			onConfigChange({
				...connector.config,
				INITIAL_URLS: value || undefined,
			});
		}
	};

	return (
		<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4 sm:space-y-6">
			<div className="space-y-1 sm:space-y-2">
				<h3 className="font-medium text-sm sm:text-base">Web Crawler Configuration</h3>
				<p className="text-xs sm:text-sm text-muted-foreground">
					Add webpages to your knowledge base for periodic indexing. Configure a Firecrawl API key
					for enhanced crawling or use the free fallback option.
				</p>
			</div>

			{/* Chat tip */}
			<div className="flex items-start gap-3 rounded-lg border border-blue-200/50 bg-blue-50/50 dark:border-blue-500/20 dark:bg-blue-950/20 p-3 text-xs sm:text-sm">
				<Info className="size-4 mt-0.5 shrink-0 text-blue-600 dark:text-blue-400" />
				<p className="text-muted-foreground">
					Want a quick answer from a webpage without indexing it? Just paste the URL directly into
					the chat instead.
				</p>
			</div>

			{/* API Key Field */}
			<div className="space-y-2">
				<Label htmlFor="api-key" className="text-xs sm:text-sm">
					Firecrawl API Key (Optional)
				</Label>
				<div className="relative">
					<Input
						id="api-key"
						type={showApiKey ? "text" : "password"}
						placeholder="fc-xxxxxxxxxxxxx"
						value={apiKey}
						onChange={(e) => handleApiKeyChange(e.target.value)}
						className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 text-xs sm:text-sm pr-10"
					/>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={() => setShowApiKey((prev) => !prev)}
						className="absolute right-1 top-1/2 -translate-y-1/2 h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
					>
						{showApiKey ? "Hide" : "Show"}
					</Button>
				</div>
				<p className="text-[10px] sm:text-xs text-muted-foreground">
					Get your API key from{" "}
					<a
						href="https://firecrawl.dev"
						target="_blank"
						rel="noopener noreferrer"
						className="text-primary hover:underline"
					>
						firecrawl.dev
					</a>
					. If not provided, will use AsyncChromiumLoader as fallback.
				</p>
			</div>

			{/* Initial URLs Field */}
			<div className="space-y-2">
				<Label htmlFor="initial-urls" className="text-xs sm:text-sm">
					Initial URLs (Optional)
				</Label>
				<Textarea
					id="initial-urls"
					placeholder="https://example.com&#10;https://docs.example.com&#10;https://blog.example.com"
					value={initialUrls}
					onChange={(e) => handleUrlsChange(e.target.value)}
					className="min-h-[100px] font-mono text-xs sm:text-sm bg-slate-400/5 dark:bg-white/5 border-slate-400/20 resize-none"
				/>
				<p className="text-[10px] sm:text-xs text-muted-foreground">
					Enter URLs to crawl (one per line). You can add more URLs later.
				</p>
			</div>

			{/* Info Alert */}
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3">
				<Info className="size-4 shrink-0" />
				<AlertDescription className="text-[10px] sm:text-xs">
					Configuration is saved when you start indexing. You can update these settings anytime from
					the connector management page.
				</AlertDescription>
			</Alert>
		</div>
	);
};
