"use client";

import { Check, Coins, Copy, Hash, Info, Timer } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRunStream } from "@/hooks/use-run-stream";
import { useScraperCapabilities } from "@/hooks/use-scraper-capabilities";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { AppError } from "@/lib/error";
import { findVerb } from "@/lib/playground/catalog";
import { formatCost, formatDuration, formatPricing } from "@/lib/playground/format";
import { buildPayload, initialFormValues, parseSchemaFields } from "@/lib/playground/json-schema";
import {
	AmazonMarketplaceHint,
	getAmazonFieldOptions,
	hasAmazonFranceValue,
} from "@/lib/playground/platform-overrides/amazon";
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

function getRunErrorMessage(error: unknown): string {
	const status = error instanceof AppError ? error.status : undefined;

	if (status === 402) {
		return "Insufficient credits. Add credits to run this API.";
	}

	if (status === 422) {
		return "Invalid input. Check the fields above and try again.";
	}

	return error instanceof Error && error.message
		? error.message
		: "Something went wrong running this API.";
}

function EndpointCopyButton({ endpoint }: { endpoint: string }) {
	const [copied, setCopied] = useState(false);

	const handleCopy = () => {
		navigator.clipboard.writeText(endpoint).then(() => {
			setCopied(true);
			setTimeout(() => setCopied(false), 1500);
		});
	};

	return (
		<Button
			type="button"
			variant="ghost"
			size="sm"
			onClick={handleCopy}
			className="h-auto max-w-full items-start justify-start gap-2 whitespace-normal rounded bg-muted/40 px-2 py-1 font-mono text-xs text-muted-foreground hover:bg-muted hover:text-foreground sm:whitespace-nowrap"
		>
			<code className="min-w-0 break-all text-left sm:break-normal">{endpoint}</code>
			{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
			<span className="sr-only">{copied ? "Copied endpoint" : "Copy endpoint"}</span>
		</Button>
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
	const previousStatusRef = useRef(run.status);
	const notifiedRunRef = useRef<string | null>(null);

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
	const endpoint = `POST /workspaces/${workspaceId}/scrapers/${platform}/${verb}`;
	const isAmazonScrape = platform === "amazon" && verb === "scrape";
	const hasAmazonFranceUrl = useMemo(() => hasAmazonFranceValue(values), [values]);

	useEffect(() => {
		const previousStatus = previousStatusRef.current;
		previousStatusRef.current = run.status;

		if (previousStatus !== "running") return;

		if (run.status === "success") {
			const key = `${run.runId ?? "run"}:success`;
			if (notifiedRunRef.current === key) return;
			notifiedRunRef.current = key;
			toast.success("API run completed.");
			return;
		}

		if (run.status === "error") {
			const key = `${run.runId ?? "run"}:error`;
			if (notifiedRunRef.current === key) return;
			notifiedRunRef.current = key;
			toast.error(getRunErrorMessage(run.error));
		}
	}, [run.status, run.runId, run.error]);

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
			<div className="space-y-6">
				{capability.description && (
					<Alert>
						<Info />
						<AlertDescription>
							<p>
								{capability.description}
								{capability.docs_url ? (
									<>
										{" "}
										<Link
											href={capability.docs_url}
											className="font-medium text-foreground underline-offset-4 hover:underline"
										>
											Read docs
										</Link>{" "}
										for more info.
									</>
								) : null}
							</p>
						</AlertDescription>
					</Alert>
				)}

				<div className="space-y-5">
					<div className="space-y-2">
						<EndpointCopyButton endpoint={endpoint} />
						<div className="text-xs text-muted-foreground">
							<span>Pricing: </span>
							<span className="font-medium tabular-nums text-foreground">
								{formatPricing(capability.pricing)}
							</span>
						</div>
					</div>
					<SchemaForm
						fields={fields}
						values={values}
						onChange={handleChange}
						disabled={isRunning}
						getFieldOptions={isAmazonScrape ? getAmazonFieldOptions : undefined}
					/>
					{isAmazonScrape ? <AmazonMarketplaceHint showFranceWarning={hasAmazonFranceUrl} /> : null}

					<div className="flex items-center gap-2">
						<Button type="button" onClick={handleRun} disabled={isRunning} className="relative">
							<span className={isRunning ? "opacity-0" : ""}>Run</span>
							{isRunning && <Spinner size="sm" className="absolute" />}
						</Button>
						{isRunning && (
							<Button type="button" variant="secondary" onClick={run.cancel}>
								Cancel
							</Button>
						)}
					</div>
				</div>

				<div className="space-y-3">
					<h2 className="text-sm font-medium text-muted-foreground">Output</h2>
					{isRunning ? (
						<RunProgressPanel latest={run.latest} events={run.events} elapsedMs={run.elapsedMs} />
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
