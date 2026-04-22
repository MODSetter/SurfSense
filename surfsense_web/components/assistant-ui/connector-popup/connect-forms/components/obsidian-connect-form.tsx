"use client";

import { Check, Copy, Info } from "lucide-react";
import { type FC, useCallback, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useApiKey } from "@/hooks/use-api-key";
import { copyToClipboard as copyToClipboardUtil } from "@/lib/utils";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const PLUGIN_RELEASES_URL =
	"https://github.com/MODSetter/SurfSense/releases?q=obsidian&expanded=true";

const BACKEND_URL =
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "https://surfsense.com";

/**
 * Obsidian connect form for the plugin-only architecture.
 *
 * The legacy `vault_path` form was removed because it only worked on
 * self-hosted with a server-side bind mount and broke for everyone else.
 * The plugin pushes data over HTTPS so this UI is purely instructional —
 * there is no backend create call here. The connector row is created
 * server-side the first time the plugin calls `POST /obsidian/connect`.
 *
 * The footer "Connect" button in `ConnectorConnectView` triggers this
 * form's submit; we just close the dialog (`onBack()`) since there's
 * nothing to validate or persist from this side.
 */
export const ObsidianConnectForm: FC<ConnectFormProps> = ({ onBack }) => {
	const { apiKey, isLoading, copied, copyToClipboard } = useApiKey();
	const [copiedUrl, setCopiedUrl] = useState(false);
	const urlCopyTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(
		undefined
	);

	const copyServerUrl = useCallback(async () => {
		const ok = await copyToClipboardUtil(BACKEND_URL);
		if (!ok) return;
		setCopiedUrl(true);
		if (urlCopyTimerRef.current) clearTimeout(urlCopyTimerRef.current);
		urlCopyTimerRef.current = setTimeout(() => setCopiedUrl(false), 2000);
	}, []);

	const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		onBack();
	};

	return (
		<div className="space-y-6 pb-6">
			{/* Form is intentionally empty so the footer Connect button is a no-op
			    that just closes the dialog (see component-level docstring). */}
			<form id="obsidian-connect-form" onSubmit={handleSubmit} />

			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3">
				<Info className="size-4 shrink-0 text-purple-500" />
				<AlertTitle className="text-xs sm:text-sm">Plugin-based sync</AlertTitle>
				<AlertDescription className="text-[10px] sm:text-xs">
					SurfSense now syncs Obsidian via an official plugin that runs inside
					Obsidian itself. Works on desktop and mobile, in cloud and self-hosted
					deployments.
				</AlertDescription>
			</Alert>

			<section className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 dark:bg-white/5">
				<div className="space-y-5 sm:space-y-6">
					{/* Step 1 — Install plugin */}
					<article>
						<header className="mb-3 flex items-center gap-2">
							<div className="flex size-7 items-center justify-center rounded-md border border-slate-400/30 text-xs font-medium">
								1
							</div>
							<h3 className="text-sm font-medium sm:text-base">Install the plugin</h3>
						</header>
						<p className="mb-3 text-[11px] text-muted-foreground sm:text-xs">
							Grab the latest SurfSense plugin release. Once it's in the community
							store, you'll also be able to install it from{" "}
							<span className="font-medium">Settings → Community plugins</span>{" "}
							inside Obsidian.
						</p>
						<a
							href={PLUGIN_RELEASES_URL}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex"
						>
							<Button type="button" variant="secondary" size="sm" className="gap-2 text-xs sm:text-sm">
								Open plugin releases
							</Button>
						</a>
					</article>

					<div className="h-px bg-border/60" />

					{/* Step 2 — Copy API key */}
					<article>
						<header className="mb-3 flex items-center gap-2">
							<div className="flex size-7 items-center justify-center rounded-md border border-slate-400/30 text-xs font-medium">
								2
							</div>
							<h3 className="text-sm font-medium sm:text-base">Copy your API key</h3>
						</header>
						<p className="mb-3 text-[11px] text-muted-foreground sm:text-xs">
							Paste this into the plugin's <span className="font-medium">API token</span>{" "}
							setting. The token expires after 24 hours. Long-lived personal access
							tokens are coming in a future release.
						</p>

						{isLoading ? (
							<div className="h-10 w-full animate-pulse rounded-md border border-border/60 bg-muted/30" />
						) : apiKey ? (
							<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5">
								<div className="min-w-0 flex-1 overflow-x-auto scrollbar-hide">
									<p className="cursor-text select-all whitespace-nowrap font-mono text-[10px] text-muted-foreground">
										{apiKey}
									</p>
								</div>
								<Button
									type="button"
									variant="ghost"
									size="icon"
									onClick={copyToClipboard}
									className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
									aria-label={copied ? "Copied" : "Copy API key"}
								>
									{copied ? (
										<Check className="size-3.5 text-green-500" />
									) : (
										<Copy className="size-3.5" />
									)}
								</Button>
							</div>
						) : (
							<p className="text-center text-xs text-muted-foreground/60">
								No API key available — try refreshing the page.
							</p>
						)}
					</article>

					<div className="h-px bg-border/60" />

					{/* Step 3 — Server URL */}
					<article>
						<header className="mb-3 flex items-center gap-2">
							<div className="flex size-7 items-center justify-center rounded-md border border-slate-400/30 text-xs font-medium">
								3
							</div>
							<h3 className="text-sm font-medium sm:text-base">Point the plugin at this server</h3>
						</header>
						<p className="text-[11px] text-muted-foreground sm:text-xs">
							For SurfSense Cloud, use the default <span className="font-medium">surfsense.com</span>.
							If you are self-hosting, set the plugin's{" "}
							<span className="font-medium">Server URL</span> to your frontend domain.
						</p>
					</article>

					<div className="h-px bg-border/60" />

					{/* Step 4 — Pick search space */}
					<article>
						<header className="mb-3 flex items-center gap-2">
							<div className="flex size-7 items-center justify-center rounded-md border border-slate-400/30 text-xs font-medium">
								4
							</div>
							<h3 className="text-sm font-medium sm:text-base">Pick this search space</h3>
						</header>
						<p className="text-[11px] text-muted-foreground sm:text-xs">
							In the plugin's <span className="font-medium">Search space</span>{" "}
							setting, choose the search space you want this vault to sync into.
							The connector will appear here automatically once the plugin makes
							its first sync.
						</p>
					</article>
				</div>
			</section>

			{getConnectorBenefits(EnumConnectorName.OBSIDIAN_CONNECTOR) && (
				<div className="space-y-2 rounded-xl border border-border bg-slate-400/5 px-3 py-4 sm:px-6 dark:bg-white/5">
					<h4 className="text-xs font-medium sm:text-sm">
						What you get with Obsidian integration:
					</h4>
					<ul className="list-disc space-y-1 pl-5 text-[10px] text-muted-foreground sm:text-xs">
						{getConnectorBenefits(EnumConnectorName.OBSIDIAN_CONNECTOR)?.map(
							(benefit) => (
								<li key={benefit}>{benefit}</li>
							)
						)}
					</ul>
				</div>
			)}
		</div>
	);
};
