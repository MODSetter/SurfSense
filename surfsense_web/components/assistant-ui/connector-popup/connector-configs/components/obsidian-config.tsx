"use client";

import { AlertTriangle, Download, Info } from "lucide-react";
import { type FC, useMemo } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { ConnectorConfigProps } from "../index";

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
 *    Phase 3 alembic) — migration banner, an "Install Plugin" CTA, and a
 *    short "how to migrate" checklist that ends with the user pressing the
 *    standard Disconnect button (which deletes this connector along with
 *    every document it previously indexed).
 * 3. **Unknown** — fallback for rows that escaped the alembic; suggests a
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
		<div className="space-y-4">
			<Alert className="border-amber-500/40 bg-amber-500/10">
				<AlertTriangle className="size-4 shrink-0 text-amber-500" />
				<AlertTitle className="text-xs sm:text-sm">
					Sync stopped — install the plugin to migrate
				</AlertTitle>
				<AlertDescription className="text-[11px] sm:text-xs leading-relaxed">
					This Obsidian connector used the legacy server-path scanner, which has been removed. The
					notes already indexed remain searchable, but they no longer reflect changes made in your
					vault.
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

			<div className="rounded-xl border border-border bg-slate-400/5 p-3 sm:p-6 dark:bg-white/5">
				<h3 className="mb-3 text-sm font-medium sm:text-base">How to migrate</h3>
				<ol className="list-decimal space-y-2 pl-5 text-[11px] leading-relaxed text-muted-foreground sm:text-xs">
					<li>Install the SurfSense Obsidian plugin using the button above.</li>
					<li>
						In Obsidian, open Settings → SurfSense, sign in, pick a search space, and wait for the
						first sync to finish.
					</li>
					<li>
						Confirm the new "Obsidian — &lt;vault&gt;" connector shows your notes, then return here
						and use the Disconnect button below to remove this legacy connector.
					</li>
				</ol>
				<p className="mt-3 text-[11px] leading-relaxed text-amber-600 dark:text-amber-400 sm:text-xs">
					Heads up: Disconnect also deletes every document this connector previously indexed. Make
					sure the plugin has finished its first sync before you disconnect, otherwise your Obsidian
					notes will disappear from search until the plugin re-indexes them.
				</p>
			</div>
		</div>
	);
};

const PluginStats: FC<{ config: Record<string, unknown> }> = ({ config }) => {
	const stats: { label: string; value: string }[] = useMemo(() => {
		const filesSynced = config.files_synced;
		// Derive from config.devices — a stored counter could drift under concurrent heartbeats.
		const deviceCount =
			config.devices && typeof config.devices === "object"
				? Object.keys(config.devices as Record<string, unknown>).length
				: null;
		return [
			{ label: "Vault", value: (config.vault_name as string) || "—" },
			{
				label: "Devices",
				value: deviceCount !== null ? deviceCount.toLocaleString() : "—",
			},
			{
				label: "Last sync",
				value: formatTimestamp(config.last_sync_at),
			},
			{
				label: "Files synced",
				value: typeof filesSynced === "number" ? filesSynced.toLocaleString() : "—",
			},
		];
	}, [config]);

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
					{stats.map((stat) => (
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
			This connector has neither plugin metadata nor a legacy marker. It may predate the migration —
			you can safely delete it and re-install the SurfSense Obsidian plugin to resume syncing.
		</AlertDescription>
	</Alert>
);
