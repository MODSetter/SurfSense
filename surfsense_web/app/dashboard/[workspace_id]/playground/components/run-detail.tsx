"use client";

import { useMemo } from "react";
import { Spinner } from "@/components/ui/spinner";
import { useScraperRun } from "@/hooks/use-scraper-runs";
import { OutputViewer } from "./output-viewer";

const MAX_OUTPUT_LINES = 200;

/** One-line label for a persisted ``run.progress`` event object. */
function progressLine(event: Record<string, unknown>): string {
	const message = typeof event.message === "string" ? event.message : undefined;
	const phase = typeof event.phase === "string" ? event.phase : undefined;
	const current = typeof event.current === "number" ? event.current : undefined;
	const total = typeof event.total === "number" ? event.total : undefined;
	const base = message || (phase ? phase.replace(/_/g, " ") : "step");
	if (current !== undefined) {
		return `${base} (${total !== undefined ? `${current}/${total}` : current})`;
	}
	return base;
}

/** Parse the stored JSONL output into objects, capped for rendering. */
function parseJsonl(text: string | null): { items: unknown[]; total: number } {
	if (!text) return { items: [], total: 0 };
	const lines = text.split("\n").filter((line) => line.trim().length > 0);
	const items: unknown[] = [];
	for (const line of lines.slice(0, MAX_OUTPUT_LINES)) {
		try {
			items.push(JSON.parse(line));
		} catch {
			items.push(line);
		}
	}
	return { items, total: lines.length };
}

export function RunDetail({ workspaceId, runId }: { workspaceId: number; runId: string }) {
	const { data: run, isLoading, error } = useScraperRun(workspaceId, runId);

	const parsed = useMemo(() => parseJsonl(run?.output_text ?? null), [run?.output_text]);

	if (isLoading) {
		return (
			<div className="flex h-32 items-center justify-center">
				<Spinner size="md" />
			</div>
		);
	}

	if (error) {
		return (
			<p className="p-4 text-sm text-destructive">
				Couldn't load run{error.message ? `: ${error.message}` : "."}
			</p>
		);
	}

	if (!run) return null;

	return (
		<div className="space-y-4 border-t border-border/60 bg-muted/10 p-4">
			{run.error && (
				<div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
					{run.error}
				</div>
			)}

			{run.progress && run.progress.length > 0 && (
				<div>
					<h4 className="mb-1.5 text-xs font-medium text-muted-foreground">Progress</h4>
					<div className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-border/60 bg-background p-3 font-mono text-xs text-muted-foreground">
						{run.progress.map((event, i) => (
							<div key={i} className="truncate">
								{progressLine(event)}
							</div>
						))}
					</div>
				</div>
			)}

			<div>
				<h4 className="mb-1.5 text-xs font-medium text-muted-foreground">Input</h4>
				<pre className="max-h-64 overflow-auto rounded-md border border-border/60 bg-background p-3 text-xs">
					<code>{JSON.stringify(run.input ?? {}, null, 2)}</code>
				</pre>
			</div>

			<div>
				<h4 className="mb-1.5 text-xs font-medium text-muted-foreground">
					Output {parsed.total > 0 && `(${parsed.total} items)`}
				</h4>
				{run.output_text ? (
					<>
						<OutputViewer
							data={{ items: parsed.items }}
							filenameBase={`${run.capability}-${run.id}`}
						/>
						{parsed.total > MAX_OUTPUT_LINES && (
							<p className="mt-2 text-xs text-muted-foreground">
								Showing first {MAX_OUTPUT_LINES} of {parsed.total} stored items.
							</p>
						)}
					</>
				) : (
					<p className="text-sm text-muted-foreground">No output stored for this run.</p>
				)}
			</div>
		</div>
	);
}
