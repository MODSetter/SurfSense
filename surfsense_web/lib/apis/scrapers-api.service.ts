import {
	type ListScraperRunsParams,
	listCapabilitiesResponse,
	listRunsResponse,
	type ScraperRunEvent,
	type StartAsyncRunResponse,
	scraperRunDetail,
	startAsyncRunResponse,
} from "@/contracts/types/scraper.types";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { readSSEStream } from "@/lib/chat/streaming-state";
import { buildBackendUrl } from "@/lib/env-config";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}/scrapers`;

class ScrapersApiService {
	/** List the platform-native verbs and their input JSON schemas. */
	listCapabilities = async (workspaceId: number | string) => {
		return baseApiService.get(`${base(workspaceId)}/capabilities`, listCapabilitiesResponse);
	};

	/**
	 * Manually invoke one verb. Returns the raw typed output (``{ items: [...] }``);
	 * the response is not schema-validated here because each verb has its own shape.
	 */
	run = async (
		workspaceId: number | string,
		platform: string,
		verb: string,
		payload: Record<string, unknown>,
		signal?: AbortSignal
	) => {
		return baseApiService.post<unknown>(`${base(workspaceId)}/${platform}/${verb}`, undefined, {
			body: payload,
			signal,
		});
	};

	listRuns = async (workspaceId: number | string, params: ListScraperRunsParams = {}) => {
		const qs = new URLSearchParams();
		if (params.limit !== undefined) qs.set("limit", String(params.limit));
		if (params.offset !== undefined) qs.set("offset", String(params.offset));
		if (params.capability) qs.set("capability", params.capability);
		if (params.status) qs.set("status", params.status);
		const query = qs.toString();
		return baseApiService.get(
			`${base(workspaceId)}/runs${query ? `?${query}` : ""}`,
			listRunsResponse
		);
	};

	getRun = async (workspaceId: number | string, runId: string) => {
		return baseApiService.get(`${base(workspaceId)}/runs/${runId}`, scraperRunDetail);
	};

	/**
	 * Start a verb as a background job (``?mode=async``). Returns the run id
	 * immediately (202); tail progress via {@link streamRunEvents}.
	 */
	runAsync = async (
		workspaceId: number | string,
		platform: string,
		verb: string,
		payload: Record<string, unknown>
	): Promise<StartAsyncRunResponse> => {
		return baseApiService.post<StartAsyncRunResponse>(
			`${base(workspaceId)}/${platform}/${verb}?mode=async`,
			startAsyncRunResponse,
			{ body: payload }
		);
	};

	/** Request cancellation of an in-progress run. */
	cancelRun = async (workspaceId: number | string, runId: string) => {
		return baseApiService.post<StartAsyncRunResponse>(
			`${base(workspaceId)}/runs/${runId}/cancel`,
			startAsyncRunResponse
		);
	};

	/**
	 * Tail a run's live progress over SSE. Yields each event until the terminal
	 * ``run.finished`` (or the stream closes / the ``signal`` aborts). Uses
	 * ``authenticatedFetch`` (desktop token + cookie auth + 401 refresh), which
	 * is why ``EventSource`` — no custom headers — can't be used here.
	 */
	streamRunEvents = async function* (
		workspaceId: number | string,
		runId: string,
		signal?: AbortSignal
	): AsyncGenerator<ScraperRunEvent> {
		const url = buildBackendUrl(`${base(workspaceId)}/runs/${runId}/events`);
		const response = await authenticatedFetch(url, {
			method: "GET",
			headers: { Accept: "text/event-stream" },
			signal,
		});
		if (!response.ok) {
			throw new Error(`Failed to open run stream (${response.status})`);
		}
		for await (const event of readSSEStream(response)) {
			// ``readSSEStream`` yields the parsed JSON object directly; our run
			// events aren't part of the chat ``SSEEvent`` union, hence the cast.
			const data = event as unknown as ScraperRunEvent;
			if (data && typeof data === "object" && typeof data.type === "string") {
				yield data;
				if (data.type === "run.finished") return;
			}
		}
	};
}

export const scrapersApiService = new ScrapersApiService();
