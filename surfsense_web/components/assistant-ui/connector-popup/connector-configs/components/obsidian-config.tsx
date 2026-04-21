"use client";

import { Info } from "lucide-react";
import { type FC, useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { connectorsApiService, type ObsidianStats } from "@/lib/apis/connectors-api.service";
import type { ConnectorConfigProps } from "../index";

function formatTimestamp(value: unknown): string {
	if (typeof value !== "string" || !value) return "—";
	const d = new Date(value);
	if (Number.isNaN(d.getTime())) return value;
	return d.toLocaleString();
}

/**
 * Obsidian connector config view.
 *
 * Read-only on purpose: the plugin owns vault identity, so the connector's
 * display name is auto-derived from `payload.vault_name` server-side on
 * every `/connect` (see `obsidian_plugin_routes.obsidian_connect`). The
 * web UI doesn't expose a Name input or a Save button for Obsidian (the
 * latter is suppressed in `connector-edit-view.tsx`).
 *
 * Renders plugin stats when connector metadata comes from the plugin.
 * If metadata is missing or malformed, we show a recovery hint.
 */
export const ObsidianConfig: FC<ConnectorConfigProps> = ({ connector }) => {
	const config = (connector.config ?? {}) as Record<string, unknown>;
	const isPlugin = config.source === "plugin";

	if (isPlugin) return <PluginStats config={config} />;
	return <UnknownConnectorState />;
};

const PluginStats: FC<{ config: Record<string, unknown> }> = ({ config }) => {
	const vaultId = typeof config.vault_id === "string" ? config.vault_id : null;
	const [stats, setStats] = useState<ObsidianStats | null>(null);
	const [statsError, setStatsError] = useState(false);

	useEffect(() => {
		if (!vaultId) return;
		let cancelled = false;
		setStats(null);
		setStatsError(false);
		connectorsApiService
			.getObsidianStats(vaultId)
			.then((result) => {
				if (!cancelled) setStats(result);
			})
			.catch((err) => {
				if (!cancelled) {
					console.error("Failed to fetch Obsidian stats", err);
					setStatsError(true);
				}
			});
		return () => {
			cancelled = true;
		};
	}, [vaultId]);

	const tileRows = useMemo(() => {
		const placeholder = statsError ? "—" : stats ? null : "…";
		return [
			{ label: "Vault", value: (config.vault_name as string) || "—" },
			{
				label: "Last sync",
				value: placeholder ?? formatTimestamp(stats?.last_sync_at ?? null),
			},
			{
				label: "Files synced",
				value:
					placeholder ??
					(typeof stats?.files_synced === "number"
						? stats.files_synced.toLocaleString()
						: "—"),
			},
		];
	}, [config.vault_name, stats, statsError]);

	return (
		<div className="space-y-4">
			<Alert className="border-emerald-500/30 bg-emerald-500/10">
				<Info className="size-4 shrink-0 text-emerald-500" />
				<AlertTitle className="text-xs sm:text-sm">Plugin connected</AlertTitle>
				<AlertDescription className="text-[11px] sm:text-xs">
					Edits in Obsidian sync over HTTPS. To stop syncing, disable or uninstall the plugin in
					Obsidian, or delete this connector.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 dark:bg-white/5">
				<h3 className="mb-3 text-sm font-medium sm:text-base">Vault status</h3>
				<dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
					{tileRows.map((stat) => (
						<div
							key={stat.label}
							className="rounded-lg border border-slate-400/20 bg-background/50 p-3"
						>
							<dt className="text-[10px] uppercase tracking-wide text-muted-foreground sm:text-xs">
								{stat.label}
							</dt>
							<dd className="mt-1 truncate text-xs font-medium sm:text-sm">{stat.value}</dd>
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
			This connector is missing plugin metadata. Delete it, then reconnect your vault from the
			SurfSense Obsidian plugin so sync can resume.
		</AlertDescription>
	</Alert>
);
