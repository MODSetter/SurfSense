"use client";

import { AlertTriangle, Info } from "lucide-react";
import { type FC, useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { connectorsApiService, type ObsidianStats } from "@/lib/apis/connectors-api.service";
import type { ConnectorConfigProps } from "../index";

const OBSIDIAN_SETUP_DOCS_URL = "/docs/connectors/obsidian";

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
 * Renders one of three modes depending on the connector's `config`:
 *
 * 1. **Plugin connector** (`config.source === "plugin"`) — read-only stats
 *    panel showing what the plugin most recently reported.
 * 2. **Legacy server-path connector** (`config.legacy === true`, set by the
 *    migration) — migration warning + docs link + explicit disconnect data-loss
 *    warning so users move to the plugin flow safely.
 * 3. **Unknown** — fallback for rows that escaped migration; suggests a
 *    clean re-install.
 */
export const ObsidianConfig: FC<ConnectorConfigProps> = ({ connector }) => {
	const config = (connector.config ?? {}) as Record<string, unknown>;
	const isLegacy = config.legacy === true;
	const isPlugin = config.source === "plugin";

	if (isLegacy) return <LegacyBanner />;
	if (isPlugin) return <PluginStats config={config} />;
	return <UnknownConnectorState />;
};

const LegacyBanner: FC = () => {
	return (
		<div className="space-y-6">
			<Alert className="border-amber-500/40 bg-amber-500/10">
				<AlertTriangle className="size-4 shrink-0 text-amber-500" />
				<AlertTitle className="text-xs sm:text-sm">
					Sync stopped, install the plugin to migrate
				</AlertTitle>
				<AlertDescription className="text-[11px] sm:text-xs leading-relaxed">
					This Obsidian connector used the legacy server-path scanner, which has been removed. The
					notes already indexed remain searchable, but they no longer reflect changes made in your
					vault.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 dark:bg-white/5">
				<h3 className="mb-3 text-sm font-medium sm:text-base">Migration required</h3>
				<p className="mb-3 text-[11px] leading-relaxed text-muted-foreground sm:text-xs">
					Follow the{" "}
					<a
						href={OBSIDIAN_SETUP_DOCS_URL}
						className="font-medium text-primary underline underline-offset-4 hover:text-primary/80"
					>
						Obsidian setup guide
					</a>{" "}
					to reconnect this vault through the plugin.
				</p>
				<p className="text-[11px] leading-relaxed text-amber-600 dark:text-amber-400 sm:text-xs">
					Heads up: Disconnect also deletes every document this connector previously indexed.
				</p>
			</div>
		</div>
	);
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
			{ label: "Vault name", value: (config.vault_name as string) || "—" },
			{
				label: "Last sync",
				value: placeholder ?? formatTimestamp(stats?.last_sync_at ?? null),
			},
			{
				label: "Files synced",
				value:
					placeholder ??
					(typeof stats?.files_synced === "number" ? stats.files_synced.toLocaleString() : "—"),
			},
		];
	}, [config.vault_name, stats, statsError]);

	return (
		<div className="space-y-4">
			<Alert className="border-emerald-500/30 bg-emerald-500/10">
				<Info className="size-4 shrink-0 text-emerald-500" />
				<AlertTitle className="text-xs sm:text-sm">Plugin connected</AlertTitle>
				<AlertDescription className="text-[11px] sm:text-xs">
					Your notes stay synced automatically. To stop syncing, disable or uninstall the plugin in
					Obsidian, or delete this connector.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl bg-slate-400/5 p-3 sm:p-6 dark:bg-white/5">
				<h3 className="mb-3 text-sm font-medium sm:text-base">Vault Status</h3>
				<dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
					{tileRows.map((stat) => (
						<div key={stat.label} className="rounded-lg bg-background/50 p-3">
							<dt className="text-xs tracking-wide text-muted-foreground sm:text-sm">
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
			This connector has neither plugin metadata nor a legacy marker. It may predate migration — you
			can safely delete it and re-install the SurfSense Obsidian plugin to resume syncing.
		</AlertDescription>
	</Alert>
);
