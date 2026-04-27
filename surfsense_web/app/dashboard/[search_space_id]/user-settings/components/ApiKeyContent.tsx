"use client";

import { Check, Copy, Info } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApiKey } from "@/hooks/use-api-key";
import { copyToClipboard as copyToClipboardUtil } from "@/lib/utils";

export function ApiKeyContent() {
	const t = useTranslations("userSettings");
	const { apiKey, isLoading, copied, copyToClipboard } = useApiKey();
	const [copiedUsage, setCopiedUsage] = useState(false);
	const usageCopyTimeoutRef = useRef<ReturnType<typeof setTimeout>>(null);

	const copyUsageToClipboard = useCallback(async () => {
		const text = `Authorization: Bearer ${apiKey || "YOUR_API_KEY"}`;
		const success = await copyToClipboardUtil(text);
		if (success) {
			setCopiedUsage(true);
			if (usageCopyTimeoutRef.current) clearTimeout(usageCopyTimeoutRef.current);
			usageCopyTimeoutRef.current = setTimeout(() => setCopiedUsage(false), 2000);
		}
	}, [apiKey]);

	return (
		<div className="space-y-6 min-w-0 overflow-hidden">
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					{t("api_key_warning_description")}
				</AlertDescription>
			</Alert>

			<div className="rounded-lg border border-border/60 bg-card p-6 min-w-0 overflow-hidden">
				<h3 className="mb-4 text-sm font-semibold tracking-tight">{t("your_api_key")}</h3>
				{isLoading ? (
					<div className="h-12 w-full animate-pulse rounded-md border border-border/60 bg-muted/30" />
				) : apiKey ? (
					<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5">
						<div className="min-w-0 flex-1 overflow-x-auto scrollbar-hide">
							<p className="font-mono text-[10px] text-muted-foreground whitespace-nowrap select-all cursor-text">
								{apiKey}
							</p>
						</div>
						<TooltipProvider>
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										onClick={copyToClipboard}
										className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
									>
										{copied ? (
											<Check className="h-3 w-3 text-green-500" />
										) : (
											<Copy className="h-3 w-3" />
										)}
									</Button>
								</TooltipTrigger>
								<TooltipContent>{copied ? t("copied") : t("copy")}</TooltipContent>
							</Tooltip>
						</TooltipProvider>
					</div>
				) : (
					<p className="text-center text-muted-foreground/60">{t("no_api_key")}</p>
				)}
			</div>

			<div className="rounded-lg border border-border/60 bg-card p-6 min-w-0 overflow-hidden">
				<h3 className="mb-2 text-sm font-semibold tracking-tight">{t("usage_title")}</h3>
				<p className="mb-4 text-[11px] text-muted-foreground/60">{t("usage_description")}</p>
				<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5">
					<div className="min-w-0 flex-1 overflow-x-auto scrollbar-hide">
						<pre className="font-mono text-[10px] text-muted-foreground whitespace-nowrap select-all cursor-text">
							<code>Authorization: Bearer {apiKey || "YOUR_API_KEY"}</code>
						</pre>
					</div>
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									onClick={copyUsageToClipboard}
									className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
								>
									{copiedUsage ? (
										<Check className="h-3 w-3 text-green-500" />
									) : (
										<Copy className="h-3 w-3" />
									)}
								</Button>
							</TooltipTrigger>
							<TooltipContent>{copiedUsage ? t("copied") : t("copy")}</TooltipContent>
						</Tooltip>
					</TooltipProvider>
				</div>
			</div>
		</div>
	);
}
