"use client";

import { Check, Copy, Shield } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApiKey } from "@/hooks/use-api-key";

export function ApiKeyContent() {
	const t = useTranslations("userSettings");
	const { apiKey, isLoading, copied, copyToClipboard } = useApiKey();

	return (
		<AnimatePresence mode="wait">
			<motion.div
				key="api-key-content"
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				exit={{ opacity: 0, y: -20 }}
				transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
				className="space-y-6"
			>
				<Alert>
					<Shield className="h-4 w-4" />
					<AlertTitle>{t("api_key_warning_title")}</AlertTitle>
					<AlertDescription>{t("api_key_warning_description")}</AlertDescription>
				</Alert>

				<div className="rounded-lg border bg-card p-6">
					<h3 className="mb-4 font-medium">{t("your_api_key")}</h3>
					{isLoading ? (
						<div className="h-12 w-full animate-pulse rounded-md bg-muted" />
					) : apiKey ? (
						<div className="flex items-center gap-2">
							<div className="flex-1 overflow-x-auto rounded-md bg-muted p-3 font-mono text-sm">
								{apiKey}
							</div>
							<TooltipProvider>
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="outline"
											size="icon"
											onClick={copyToClipboard}
											className="shrink-0"
										>
											{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
										</Button>
									</TooltipTrigger>
									<TooltipContent>{copied ? t("copied") : t("copy")}</TooltipContent>
								</Tooltip>
							</TooltipProvider>
						</div>
					) : (
						<p className="text-center text-muted-foreground">{t("no_api_key")}</p>
					)}
				</div>

				<div className="rounded-lg border bg-card p-6">
					<h3 className="mb-2 font-medium">{t("usage_title")}</h3>
					<p className="mb-4 text-sm text-muted-foreground">{t("usage_description")}</p>
					<pre className="overflow-x-auto rounded-md bg-muted p-3 text-sm">
						<code>Authorization: Bearer {apiKey || "YOUR_API_KEY"}</code>
					</pre>
				</div>
			</motion.div>
		</AnimatePresence>
	);
}
