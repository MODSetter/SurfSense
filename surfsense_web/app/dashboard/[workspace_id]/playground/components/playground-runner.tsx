"use client";

import { AlertTriangle, Coins, Hash, Loader2, Play, Timer, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRunStream } from "@/hooks/use-run-stream";
import { useScraperCapabilities } from "@/hooks/use-scraper-capabilities";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { AbortedError, AppError } from "@/lib/error";
import { findVerb } from "@/lib/playground/catalog";
import { formatCost, formatDuration } from "@/lib/playground/format";
import { buildPayload, initialFormValues, parseSchemaFields } from "@/lib/playground/json-schema";
import { ApiReference } from "./api-reference";
import { OutputViewer } from "./output-viewer";
import { RunProgressPanel } from "./run-progress-panel";
import { SchemaForm } from "./schema-form";

interface PlaygroundRunnerProps {
	workspaceId: number;
	platform: string;
	verb: string;
}

const MAX_OUTPUT_LINES = 200;

/** Parse the stored JSONL output into objects, capped for rendering. */
function parseJsonlOutput(text: string | null | undefined): { items: unknown[] } {
	if (!text) return { items: [] };
	const lines = text.split("\n").filter((line) => line.trim().length > 0);
	const items: unknown[] = [];
	for (const line of lines.slice(0, MAX_OUTPUT_LINES)) {
		try {
			items.push(JSON.parse(line));
		} catch {
			items.push(line);
		}
	}
	return { items };
}

function RunStat({
	icon: Icon,
	label,
	value,
}: {
	icon: typeof Hash;
	label: string;
	value: string;
}) {
	return (
		<div className="flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5">
			<Icon className="h-3.5 w-3.5 text-muted-foreground" />
			<span className="text-xs text-muted-foreground">{label}</span>
			<span className="text-xs font-medium tabular-nums">{value}</span>
		</div>
	);
}

function ErrorPanel({ error, workspaceId }: { error: unknown; workspaceId: number }) {
	if (error instanceof AbortedError) {
		return null;
	}
	const status = error instanceof AppError ? error.status : undefined;

	if (status === 402) {
		return (
			<div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
				<p className="font-medium text-destructive">Insufficient credits</p>
				<p className="mt-1 text-muted-foreground">You don't have enough credits to run this API.</p>
				<Button asChild size="sm" variant="outline" className="mt-3">
					<Link href={`/dashboard/${workspaceId}/buy-more`}>Buy credits</Link>
				</Button>
			</div>
		);
	}

	const message =
		status === 422
			? "Invalid input. Check the fields above and try again."
			: error instanceof Error && error.message
				? error.message
				: "Something went wrong running this API.";

	return (
		<div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
			<AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
			<span>{message}</span>
		</div>
	);
}

export function PlaygroundRunner({ workspaceId, platform, verb }: PlaygroundRunnerProps) {
	const catalogVerb = findVerb(platform, verb);
	const {
		data: capabilities,
		isLoading,
		error: capabilitiesError,
	} = useScraperCapabilities(workspaceId);

	const capability = useMemo(() => {
		if (!capabilities) return undefined;
		const name = catalogVerb?.name ?? `${platform}.${verb}`;
		return capabilities.find((c) => c.name === name);
	}, [capabilities, catalogVerb, platform, verb]);

	const fields = useMemo(() => parseSchemaFields(capability?.input_schema), [capability]);

	const [values, setValues] = useState<Record<string, unknown>>({});
	const run = useRunStream(workspaceId);
	const isRunning = run.status === "running";

	// Seed form defaults once the schema is available.
	useEffect(() => {
		if (fields.length > 0) {
			setValues(initialFormValues(fields));
		}
	}, [fields]);

	// Survive a refresh: if this verb's newest run is still ``running``, re-attach
	// to its live stream instead of showing an idle form.
	const reattachedRef = useRef(false);
	const { reattach } = run;
	useEffect(() => {
		if (reattachedRef.current || !capability) return;
		reattachedRef.current = true;
		let cancelled = false;
		(async () => {
			try {
				const recent = await scrapersApiService.listRuns(workspaceId, {
					capability: capability.name,
					limit: 1,
				});
				const top = recent[0];
				if (!cancelled && top && top.status === "running") {
					reattach(top.id);
				}
			} catch {
				// Best-effort reattach; a fresh run still works.
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [capability, workspaceId, reattach]);

	const handleChange = (name: string, value: unknown) => {
		setValues((prev) => ({ ...prev, [name]: value }));
	};

	const handleRun = useCallback(() => {
		const payload = buildPayload(fields, values);
		void run.start(platform, verb, payload);
	}, [fields, values, platform, verb, run]);

	const output = useMemo(
		() => (run.detail ? parseJsonlOutput(run.detail.output_text) : null),
		[run.detail]
	);

	if (isLoading) {
		return (
			<div className="flex h-64 items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (capabilitiesError) {
		return (
			<div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
				Couldn't load API definitions
				{capabilitiesError.message ? `: ${capabilitiesError.message}` : "."}
			</div>
		);
	}

	if (!capability || !catalogVerb) {
		return (
			<div className="rounded-md border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
				Unknown API: {platform}.{verb}
			</div>
		);
	}

	return (
		<div className="space-y-10">
			<div className="grid gap-6 lg:grid-cols-2">
				<div className="space-y-5">
					<div>
						<h1 className="text-lg font-semibold">
							{catalogVerb.label} <span className="text-muted-foreground">· {platform}</span>
						</h1>
						{capability.description && (
							<p className="mt-1 text-sm text-muted-foreground">{capability.description}</p>
						)}
						<code className="mt-2 inline-block rounded bg-muted/40 px-1.5 py-0.5 text-xs text-muted-foreground">
							POST /workspaces/{workspaceId}/scrapers/{platform}/{verb}
						</code>
					</div>

					<SchemaForm
						fields={fields}
						values={values}
						onChange={handleChange}
						disabled={isRunning}
					/>

					<div className="flex items-center gap-2">
						<Button type="button" onClick={handleRun} disabled={isRunning} className="gap-1.5">
							{isRunning ? (
								<Loader2 className="h-4 w-4 animate-spin" />
							) : (
								<Play className="h-4 w-4" />
							)}
							Run
						</Button>
						{isRunning && (
							<Button type="button" variant="outline" onClick={run.cancel} className="gap-1.5">
								<X className="h-4 w-4" />
								Cancel
							</Button>
						)}
					</div>

					{run.status === "error" && <ErrorPanel error={run.error} workspaceId={workspaceId} />}
				</div>

				<div className="space-y-3">
					<h2 className="text-sm font-medium text-muted-foreground">Output</h2>
					{isRunning ? (
						<RunProgressPanel
							latest={run.latest}
							events={run.events}
							elapsedMs={run.elapsedMs}
						/>
					) : run.status === "cancelled" ? (
						<div className="flex h-64 items-center justify-center rounded-md border border-border/60 px-4 text-center text-sm text-muted-foreground">
							Run cancelled.
						</div>
					) : run.status === "success" && output ? (
						<>
							<div className="flex flex-wrap gap-2">
								<RunStat
									icon={Hash}
									label="Items"
									value={String(run.detail?.item_count ?? output.items.length)}
								/>
								<RunStat
									icon={Timer}
									label="Time"
									value={formatDuration(run.detail?.duration_ms ?? run.elapsedMs)}
								/>
								<RunStat icon={Coins} label="Cost" value={formatCost(run.detail?.cost_micros)} />
							</div>
							<OutputViewer data={output} filenameBase={`${platform}-${verb}`} />
						</>
					) : (
						<div className="flex h-64 items-center justify-center rounded-md border border-dashed border-border/60 px-4 text-center text-sm text-muted-foreground">
							Run the API to see output here.
						</div>
					)}
				</div>
			</div>

			<ApiReference
				workspaceId={workspaceId}
				platform={platform}
				verb={verb}
				fields={fields}
				inputSchema={capability.input_schema}
				outputSchema={capability.output_schema}
			/>
		</div>
	);
}
