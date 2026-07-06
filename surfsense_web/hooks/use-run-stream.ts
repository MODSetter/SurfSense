"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ScraperRunDetail, ScraperRunEvent } from "@/contracts/types/scraper.types";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export type RunStatus = "idle" | "running" | "success" | "error" | "cancelled";

/** Keep the live progress log bounded — it's a scrolling view, not a record. */
const MAX_LOG = 200;

interface RunStreamState {
	runId: string | null;
	status: RunStatus;
	/** Recent ``run.progress`` events, newest last. */
	events: ScraperRunEvent[];
	/** Latest lifecycle/progress event, for the headline status line. */
	latest: ScraperRunEvent | null;
	/** Fetched once on successful finish (carries output + authoritative metrics). */
	detail: ScraperRunDetail | null;
	/** Raw error (AppError for start failures, Error for stream/terminal failures). */
	error: unknown;
	elapsedMs: number;
}

const INITIAL: RunStreamState = {
	runId: null,
	status: "idle",
	events: [],
	latest: null,
	detail: null,
	error: null,
	elapsedMs: 0,
};

/**
 * Drive a single async scraper run: start it, tail its SSE progress, and expose
 * a small reactive state for the playground. Also supports re-attaching to a run
 * that is still ``running`` (e.g. after a page refresh).
 */
export function useRunStream(workspaceId: number) {
	const queryClient = useQueryClient();
	const [state, setState] = useState<RunStreamState>(INITIAL);
	const abortRef = useRef<AbortController | null>(null);
	const runIdRef = useRef<string | null>(null);
	const startedAtRef = useRef<number>(0);

	// Live elapsed timer, ticking only while a run is in flight.
	useEffect(() => {
		if (state.status !== "running") return;
		const id = setInterval(() => {
			setState((s) => ({ ...s, elapsedMs: Date.now() - startedAtRef.current }));
		}, 500);
		return () => clearInterval(id);
	}, [state.status]);

	// Abort any in-flight stream on unmount.
	useEffect(() => () => abortRef.current?.abort(), []);

	const consume = useCallback(
		async (runId: string, signal: AbortSignal) => {
			try {
				for await (const ev of scrapersApiService.streamRunEvents(workspaceId, runId, signal)) {
					if (ev.type === "run.finished") {
						const finalStatus = (ev.status as RunStatus) || "success";
						let detail: ScraperRunDetail | null = null;
						if (finalStatus === "success") {
							try {
								detail = await scrapersApiService.getRun(workspaceId, runId);
							} catch {
								detail = null;
							}
						}
						setState((s) => ({
							...s,
							status: finalStatus,
							detail,
							error: ev.error ? new Error(ev.error) : s.error,
						}));
						queryClient.invalidateQueries({
							queryKey: cacheKeys.scrapers.runs(workspaceId),
						});
						return;
					}
					if (ev.type === "run.heartbeat") continue;
					setState((s) => ({
						...s,
						latest: ev,
						events:
							ev.type === "run.progress"
								? [...s.events.slice(-(MAX_LOG - 1)), ev]
								: s.events,
					}));
				}
			} catch (e) {
				if (signal.aborted) return;
				setState((s) =>
					s.status === "running" ? { ...s, status: "error", error: e } : s
				);
			}
		},
		[workspaceId, queryClient]
	);

	const start = useCallback(
		async (platform: string, verb: string, payload: Record<string, unknown>) => {
			abortRef.current?.abort();
			const controller = new AbortController();
			abortRef.current = controller;
			startedAtRef.current = Date.now();
			setState({ ...INITIAL, status: "running" });
			try {
				const started = await scrapersApiService.runAsync(
					workspaceId,
					platform,
					verb,
					payload
				);
				runIdRef.current = started.run_id;
				setState((s) => ({ ...s, runId: started.run_id }));
				void consume(started.run_id, controller.signal);
			} catch (e) {
				runIdRef.current = null;
				setState((s) => ({ ...s, status: "error", error: e }));
			}
		},
		[workspaceId, consume]
	);

	const reattach = useCallback(
		(runId: string) => {
			abortRef.current?.abort();
			const controller = new AbortController();
			abortRef.current = controller;
			startedAtRef.current = Date.now();
			runIdRef.current = runId;
			setState({ ...INITIAL, runId, status: "running" });
			void consume(runId, controller.signal);
		},
		[consume]
	);

	const cancel = useCallback(async () => {
		const runId = runIdRef.current;
		if (!runId) return;
		// The stream delivers the terminal ``run.finished`` (cancelled) which flips
		// our state; the request just asks the server to stop.
		try {
			await scrapersApiService.cancelRun(workspaceId, runId);
		} catch {
			// Best-effort: if the run already finished the stream reflects the truth.
		}
	}, [workspaceId]);

	const reset = useCallback(() => {
		abortRef.current?.abort();
		runIdRef.current = null;
		setState(INITIAL);
	}, []);

	return { ...state, start, cancel, reattach, reset };
}
