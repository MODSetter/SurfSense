"use client";
import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useQuery as useReactQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { Run, RunStepResult, RunSummary } from "@/contracts/types/automation.types";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queries } from "@/zero/queries";

const DEFAULT_LIMIT = 50;

/**
 * Thin live row sourced from Zero. Strict superset of {@link RunSummary} —
 * existing consumers that only look at the summary fields keep working,
 * while the run detail panel can read ``step_results`` directly for the
 * live step ticker without a second REST round-trip.
 */
export interface LiveRunSummary extends RunSummary {
	step_results: RunStepResult[];
}

export interface UseAutomationRunsOptions {
	limit?: number;
}

interface UseAutomationRunsResult {
	data: { items: LiveRunSummary[]; total: number } | undefined;
	isLoading: boolean;
	error: Error | null;
}

/**
 * Live run history for one automation, newest-first. Sourced from Zero's
 * thin ``automation_runs`` publication so status and per-step progress
 * tick in real time without polling. Heavy fields (output, artifacts,
 * inputs, error, definition_snapshot) are still fetched lazily via
 * {@link useAutomationRun}.
 */
export function useAutomationRuns(
	automationId: number | undefined,
	{ limit = DEFAULT_LIMIT }: UseAutomationRunsOptions = {}
): UseAutomationRunsResult {
	const [rows, result] = useZeroQuery(
		queries.automationRuns.byAutomation({ automationId: automationId ?? -1 })
	);

	const items = useMemo<LiveRunSummary[]>(() => {
		if (!automationId) return [];
		return rows.slice(0, limit).map(toLiveRunSummary);
	}, [automationId, rows, limit]);

	const total = automationId ? rows.length : 0;

	// Pre-hydration window: nothing visible AND Zero hasn't confirmed
	// completeness yet. After the first sync (even an empty set) we stop
	// showing the skeleton so the empty-state copy can take over.
	const isLoading = !!automationId && result.type !== "complete" && rows.length === 0;

	return {
		data: automationId ? { items, total } : undefined,
		isLoading,
		error: null,
	};
}

/**
 * Full run record (definition snapshot, inputs, output, artifacts, error).
 * Stays on REST: these fields are large and largely static after the run
 * finishes, so they're not worth replicating to every connected client.
 */
export function useAutomationRun(
	automationId: number | undefined,
	runId: number | undefined,
	options: { enabled?: boolean } = {}
) {
	const { enabled = true } = options;
	return useReactQuery<Run, Error>({
		queryKey: cacheKeys.automations.run(automationId ?? 0, runId ?? 0),
		queryFn: () => automationsApiService.getRun(automationId as number, runId as number),
		enabled: enabled && !!automationId && !!runId,
		staleTime: 30_000,
	});
}

interface ZeroAutomationRunRow {
	id: number;
	automationId: number;
	triggerId?: number | null;
	status: string;
	stepResults: unknown;
	startedAt?: number | null;
	finishedAt?: number | null;
	createdAt: number;
}

/** Adapt a Zero camelCase row (epoch ms timestamps) to the snake_case
 * ISO-string ``RunSummary`` shape the existing UI already consumes. */
function toLiveRunSummary(row: ZeroAutomationRunRow): LiveRunSummary {
	return {
		id: row.id,
		automation_id: row.automationId,
		trigger_id: row.triggerId ?? null,
		status: row.status as RunSummary["status"],
		started_at: row.startedAt ? new Date(row.startedAt).toISOString() : null,
		finished_at: row.finishedAt ? new Date(row.finishedAt).toISOString() : null,
		created_at: new Date(row.createdAt).toISOString(),
		step_results: Array.isArray(row.stepResults) ? (row.stepResults as RunStepResult[]) : [],
	};
}
