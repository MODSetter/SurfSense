"use client";

import { ArrowRight, History, KeyRound } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { useScraperCapabilities } from "@/hooks/use-scraper-capabilities";
import { PLAYGROUND_PLATFORMS } from "@/lib/playground/catalog";
import { formatPricing } from "@/lib/playground/format";

export function PlaygroundIndex({ workspaceId }: { workspaceId: number }) {
	const base = `/dashboard/${workspaceId}/playground`;

	// The grid renders from the static catalog immediately; pricing fills in
	// once the capabilities fetch lands (blank while loading, never blocking).
	const { data: capabilities } = useScraperCapabilities(workspaceId);
	const pricingByName = useMemo(
		() => new Map(capabilities?.map((c) => [c.name, formatPricing(c.pricing)])),
		[capabilities]
	);

	return (
		<div className="space-y-8">
			<div>
				<h1 className="text-xl font-semibold text-foreground md:text-2xl">API Playground</h1>
				<p className="mt-1 text-sm text-muted-foreground">
					Manually run SurfSense's platform-native APIs and inspect their output. Every run is
					captured under Runs.
				</p>
			</div>

			<div className="grid gap-3 sm:grid-cols-2">
				<Link
					href={`${base}/runs`}
					className="flex items-center justify-between rounded-lg border border-border/60 bg-accent/40 px-4 py-3 transition-colors hover:bg-accent"
				>
					<div className="flex items-center gap-3">
						<History className="h-5 w-5 text-muted-foreground" />
						<div>
							<p className="text-sm font-medium">Runs</p>
							<p className="text-xs text-muted-foreground">See every API run in this workspace</p>
						</div>
					</div>
					<ArrowRight className="h-4 w-4 text-muted-foreground" />
				</Link>
				<Link
					href={`${base}/api-keys`}
					className="flex items-center justify-between rounded-lg border border-border/60 bg-accent/40 px-4 py-3 transition-colors hover:bg-accent"
				>
					<div className="flex items-center gap-3">
						<KeyRound className="h-5 w-5 text-muted-foreground" />
						<div>
							<p className="text-sm font-medium">API Keys</p>
							<p className="text-xs text-muted-foreground">
								Enable workspace access and manage keys
							</p>
						</div>
					</div>
					<ArrowRight className="h-4 w-4 text-muted-foreground" />
				</Link>
			</div>

			<div className="space-y-6">
				{PLAYGROUND_PLATFORMS.map((platform) => (
					<div key={platform.id} className="space-y-3">
						<div className="flex items-center gap-2">
							<platform.icon className="h-4 w-4 text-muted-foreground" />
							<h2 className="text-sm font-semibold">{platform.label}</h2>
						</div>
						<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
							{platform.verbs.map((verb) => (
								<Link
									key={verb.name}
									href={`${base}/${platform.id}/${verb.verb}`}
									className="group flex flex-col rounded-lg border border-border/60 p-4 transition-colors hover:border-border hover:bg-muted/30"
								>
									<div className="flex items-center justify-between">
										<span className="text-sm font-medium">{verb.label}</span>
										<ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
									</div>
									<code className="mt-2 text-xs text-muted-foreground">{verb.name}</code>
									{pricingByName.has(verb.name) ? (
										<span className="mt-2 text-xs tabular-nums text-muted-foreground">
											{pricingByName.get(verb.name)}
										</span>
									) : null}
								</Link>
							))}
						</div>
					</div>
				))}
			</div>
		</div>
	);
}
