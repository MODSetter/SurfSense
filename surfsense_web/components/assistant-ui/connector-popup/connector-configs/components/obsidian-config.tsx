"use client";

import { AlertTriangle, Check, Copy, Download, Info } from "lucide-react";
import { type FC, useCallback, useMemo, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApiKey } from "@/hooks/use-api-key";
import { copyToClipboard as copyToClipboardUtil } from "@/lib/utils";
import type { ConnectorConfigProps } from "../index";

export interface ObsidianConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

const PLUGIN_RELEASES_URL =
	"https://github.com/MODSetter/SurfSense/releases?q=obsidian&expanded=true";

function formatTimestamp(value: unknown): string {
	if (typeof value !== "string" || !value) return "—";
	const d = new Date(value);
	if (Number.isNaN(d.getTime())) return value;
	return d.toLocaleString();
}

/**
 * Obsidian connector config view.
 *
 * Renders one of two modes depending on the connector's `config`:
 *
 * 1. **Plugin connector** (`config.source === "plugin"`) — read-only stats
 *    panel showing what the plugin most recently reported.
 * 2. **Legacy server-path connector** (`config.legacy === true`, set by the
 *    Phase 3 alembic) — migration banner plus an "Install Plugin" CTA.
 *    The user's existing notes stay searchable; only background sync stops.
 */
export const ObsidianConfig: FC<ObsidianConfigProps> = ({
	connector,
	onNameChange,
}) => {
	const [name, setName] = useState<string>(connector.name || "");
	const config = (connector.config ?? {}) as Record<string, unknown>;
	const isLegacy = config.legacy === true;
	const isPlugin = config.source === "plugin";

	const handleNameChange = (value: string) => {
		setName(value);
		onNameChange?.(value);
	};

	return (
		<div className="space-y-6">
			{/* Connector name (always editable) */}
			<div className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 space-y-3 sm:space-y-4 dark:bg-white/5">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="My Obsidian Vault"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this connector.
					</p>
				</div>
			</div>

			{isLegacy ? (
				<LegacyBanner />
			) : isPlugin ? (
				<PluginStats config={config} />
			) : (
				<UnknownConnectorState />
			)}
		</div>
	);
};

const LegacyBanner: FC = () => {
	return (
		<div className="space-y-4">
			<Alert className="border-amber-500/40 bg-amber-500/10">
				<AlertTriangle className="size-4 shrink-0 text-amber-500" />
				<AlertTitle className="text-xs sm:text-sm">
					This connector has been migrated
				</AlertTitle>
				<AlertDescription className="text-[11px] sm:text-xs leading-relaxed">
					This Obsidian connector used the legacy server-path method, which has
					been removed. To resume syncing, install the SurfSense Obsidian
					plugin and connect with this account. Your existing notes remain
					searchable. After the plugin re-indexes your vault, you can delete
					this connector to remove older copies.
				</AlertDescription>
			</Alert>

			<a
				href={PLUGIN_RELEASES_URL}
				target="_blank"
				rel="noopener noreferrer"
				className="inline-flex"
			>
				<Button type="button" variant="outline" size="sm" className="gap-2">
					<Download className="size-3.5" />
					Install the plugin
				</Button>
			</a>

			<ApiKeyReminder />
		</div>
	);
};

const PluginStats: FC<{ config: Record<string, unknown> }> = ({ config }) => {
	const stats: { label: string; value: string }[] = useMemo(() => {
		const filesSynced = config.files_synced;
		return [
			{ label: "Vault", value: (config.vault_name as string) || "—" },
			{
				label: "Plugin version",
				value: (config.plugin_version as string) || "—",
			},
			{
				label: "Device",
				value:
					(config.device_label as string) ||
					(config.device_id as string) ||
					"—",
			},
			{
				label: "Last sync",
				value: formatTimestamp(config.last_sync_at),
			},
			{
				label: "Files synced",
				value:
					typeof filesSynced === "number" ? filesSynced.toLocaleString() : "—",
			},
		];
	}, [config]);

	return (
		<div className="space-y-4">
			<Alert className="border-emerald-500/30 bg-emerald-500/10">
				<Info className="size-4 shrink-0 text-emerald-500" />
				<AlertTitle className="text-xs sm:text-sm">Plugin connected</AlertTitle>
				<AlertDescription className="text-[11px] sm:text-xs">
					Edits in Obsidian sync over HTTPS. To stop syncing, disable or
					uninstall the plugin in Obsidian, or delete this connector.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 dark:bg-white/5">
				<h3 className="mb-3 text-sm font-medium sm:text-base">Vault status</h3>
				<dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
					{stats.map((stat) => (
						<div
							key={stat.label}
							className="rounded-lg border border-slate-400/20 bg-background/50 p-3"
						>
							<dt className="text-[10px] uppercase tracking-wide text-muted-foreground sm:text-xs">
								{stat.label}
							</dt>
							<dd className="mt-1 truncate text-xs font-medium sm:text-sm">
								{stat.value}
							</dd>
						</div>
					))}
				</dl>
			</div>
		</div>
	);
};

const UnknownConnectorState: FC = () => (
	<Alert>
		<Info className="size-4 shrink-0" />
		<AlertTitle className="text-xs sm:text-sm">Unrecognized config</AlertTitle>
		<AlertDescription className="text-[11px] sm:text-xs">
			This connector has neither plugin metadata nor a legacy marker. It may
			predate the migration — you can safely delete it and re-install the
			SurfSense Obsidian plugin to resume syncing.
		</AlertDescription>
	</Alert>
);

const ApiKeyReminder: FC = () => {
	const { apiKey, isLoading, copied, copyToClipboard } = useApiKey();
	const [copiedUrl, setCopiedUrl] = useState(false);
	const urlCopyTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(
		undefined
	);

	const backendUrl =
		process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "https://api.surfsense.com";

	const copyServerUrl = useCallback(async () => {
		const ok = await copyToClipboardUtil(backendUrl);
		if (!ok) return;
		setCopiedUrl(true);
		if (urlCopyTimerRef.current) clearTimeout(urlCopyTimerRef.current);
		urlCopyTimerRef.current = setTimeout(() => setCopiedUrl(false), 2000);
	}, [backendUrl]);

	return (
		<div className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 space-y-3 dark:bg-white/5">
			<h3 className="text-sm font-medium sm:text-base">
				Plugin connection details
			</h3>
			<p className="text-[11px] text-muted-foreground sm:text-xs">
				Paste these into the plugin's settings inside Obsidian.
			</p>

			<div className="space-y-2">
				<Label className="text-xs sm:text-sm">API token</Label>
				{isLoading ? (
					<div className="h-9 w-full animate-pulse rounded-md border border-border/60 bg-muted/30" />
				) : (
					<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5">
						<div className="min-w-0 flex-1 overflow-x-auto scrollbar-hide">
							<p className="cursor-text select-all whitespace-nowrap font-mono text-[10px] text-muted-foreground">
								{apiKey || "No API key available"}
							</p>
						</div>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={copyToClipboard}
							disabled={!apiKey}
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
				)}
				<p className="text-[10px] text-muted-foreground sm:text-xs">
					Token expires after 24 hours; long-lived tokens are coming in a
					future release.
				</p>
			</div>

			<div className="space-y-2">
				<Label className="text-xs sm:text-sm">Server URL</Label>
				<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5">
					<div className="min-w-0 flex-1 overflow-x-auto scrollbar-hide">
						<p className="cursor-text select-all whitespace-nowrap font-mono text-[10px] text-muted-foreground">
							{backendUrl}
						</p>
					</div>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={copyServerUrl}
						className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
						aria-label={copiedUrl ? "Copied" : "Copy server URL"}
					>
						{copiedUrl ? (
							<Check className="size-3.5 text-green-500" />
						) : (
							<Copy className="size-3.5" />
						)}
					</Button>
				</div>
			</div>
		</div>
	);
};
