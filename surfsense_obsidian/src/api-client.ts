import { requestUrl, type RequestUrlParam, type RequestUrlResponse } from "obsidian";
import type {
	ConnectResponse,
	DeleteAck,
	HealthResponse,
	ManifestResponse,
	NotePayload,
	RenameAck,
	RenameItem,
	SearchSpace,
	SyncAck,
} from "./types";

/**
 * SurfSense backend client used by the Obsidian plugin.
 *
 * Mobile-safety contract (must hold for every transitive import):
 *   - Use Obsidian `requestUrl` only — no `fetch`, no `axios`, no
 *     `node:http`, no `node:https`. CORS is bypassed and mobile works.
 *   - No top-level `node:*` imports anywhere reachable from this file.
 *   - Hashing happens elsewhere via Web Crypto, not `node:crypto`.
 *
 * Auth + wire contract:
 *   - Every request carries `Authorization: Bearer <token>` only. No
 *     custom headers — the backend identifies the caller from the JWT
 *     and feature-detects the API via the `capabilities` array on
 *     `/health` and `/connect`.
 *   - 401 surfaces as `AuthError` so the orchestrator can show the
 *     "token expired, paste a fresh one" UX.
 *   - HealthResponse / ConnectResponse use index signatures so any
 *     additive backend field (e.g. new capabilities) parses without
 *     breaking the decoder. This mirrors `ConfigDict(extra='ignore')`
 *     on the server side.
 */

export class AuthError extends Error {
	constructor(message: string) {
		super(message);
		this.name = "AuthError";
	}
}

export class TransientError extends Error {
	readonly status: number;
	constructor(status: number, message: string) {
		super(message);
		this.name = "TransientError";
		this.status = status;
	}
}

export class PermanentError extends Error {
	readonly status: number;
	constructor(status: number, message: string) {
		super(message);
		this.name = "PermanentError";
		this.status = status;
	}
}

/** 404 `VAULT_NOT_REGISTERED` — `/connect` hasn't committed yet; retry after reconnect. */
export class VaultNotRegisteredError extends TransientError {
	constructor(message: string) {
		super(404, message);
		this.name = "VaultNotRegisteredError";
	}
}

export interface ApiClientOptions {
	getServerUrl: () => string;
	getToken: () => string;
	onAuthError?: () => void;
}

const AUTH_BLOCK_MS = 60_000;

export class SurfSenseApiClient {
	private readonly opts: ApiClientOptions;
	private authBlockedUntil = 0;

	constructor(opts: ApiClientOptions) {
		this.opts = opts;
	}

	updateOptions(partial: Partial<ApiClientOptions>): void {
		Object.assign(this.opts, partial);
	}

	resetAuthBlock(): void {
		this.authBlockedUntil = 0;
	}

	async health(): Promise<HealthResponse> {
		return await this.request<HealthResponse>("GET", "/api/v1/obsidian/health");
	}

	async listSearchSpaces(): Promise<SearchSpace[]> {
		const resp = await this.request<SearchSpace[] | { items: SearchSpace[] }>(
			"GET",
			"/api/v1/searchspaces/"
		);
		if (Array.isArray(resp)) return resp;
		if (resp && Array.isArray((resp as { items?: SearchSpace[] }).items)) {
			return (resp as { items: SearchSpace[] }).items;
		}
		return [];
	}

	async verifyToken(): Promise<{ ok: true; health: HealthResponse }> {
		// /health is gated by current_active_user, so a successful response
		// transitively proves the token works. Cheaper than fetching a list.
		const health = await this.health();
		return { ok: true, health };
	}

	async connect(input: {
		searchSpaceId: number;
		vaultId: string;
		vaultName: string;
		vaultFingerprint: string;
	}): Promise<ConnectResponse> {
		return await this.request<ConnectResponse>(
			"POST",
			"/api/v1/obsidian/connect",
			{
				vault_id: input.vaultId,
				vault_name: input.vaultName,
				search_space_id: input.searchSpaceId,
				vault_fingerprint: input.vaultFingerprint,
			}
		);
	}

	/** POST /sync — `failed[]` are paths whose `status === "error"` for retry. */
	async syncBatch(input: {
		vaultId: string;
		notes: NotePayload[];
	}): Promise<{ indexed: number; failed: string[] }> {
		const resp = await this.request<SyncAck>(
			"POST",
			"/api/v1/obsidian/sync",
			{ vault_id: input.vaultId, notes: input.notes }
		);
		const failed = resp.items
			.filter((it) => it.status === "error")
			.map((it) => it.path);
		return { indexed: resp.indexed, failed };
	}

	/** POST /rename — `"missing"` counts as success; only `"error"` is retried. */
	async renameBatch(input: {
		vaultId: string;
		renames: Pick<RenameItem, "oldPath" | "newPath">[];
	}): Promise<{
		renamed: number;
		failed: Array<{ oldPath: string; newPath: string }>;
	}> {
		const resp = await this.request<RenameAck>(
			"POST",
			"/api/v1/obsidian/rename",
			{
				vault_id: input.vaultId,
				renames: input.renames.map((r) => ({
					old_path: r.oldPath,
					new_path: r.newPath,
				})),
			}
		);
		const failed = resp.items
			.filter((it) => it.status === "error")
			.map((it) => ({ oldPath: it.old_path, newPath: it.new_path }));
		return { renamed: resp.renamed, failed };
	}

	/** DELETE /notes — `"missing"` counts as success; only `"error"` is retried. */
	async deleteBatch(input: {
		vaultId: string;
		paths: string[];
	}): Promise<{ deleted: number; failed: string[] }> {
		const resp = await this.request<DeleteAck>(
			"DELETE",
			"/api/v1/obsidian/notes",
			{ vault_id: input.vaultId, paths: input.paths }
		);
		const failed = resp.items
			.filter((it) => it.status === "error")
			.map((it) => it.path);
		return { deleted: resp.deleted, failed };
	}

	async getManifest(vaultId: string): Promise<ManifestResponse> {
		return await this.request<ManifestResponse>(
			"GET",
			`/api/v1/obsidian/manifest?vault_id=${encodeURIComponent(vaultId)}`
		);
	}

	private async request<T>(
		method: RequestUrlParam["method"],
		path: string,
		body?: unknown
	): Promise<T> {
		const baseUrl = this.opts.getServerUrl().replace(/\/+$/, "");
		const token = this.opts.getToken();
		if (!token) {
			throw new AuthError("Missing API token. Open SurfSense settings to paste one.");
		}
		if (Date.now() < this.authBlockedUntil) {
			throw new AuthError("Token rejected. Paste a fresh one in settings.");
		}
		const headers: Record<string, string> = {
			Authorization: `Bearer ${token}`,
			Accept: "application/json",
		};
		if (body !== undefined) headers["Content-Type"] = "application/json";

		let resp: RequestUrlResponse;
		try {
			resp = await requestUrl({
				url: `${baseUrl}${path}`,
				method,
				headers,
				body: body === undefined ? undefined : JSON.stringify(body),
				throw: false,
			});
		} catch (err) {
			throw new TransientError(0, `Network error: ${(err as Error).message}`);
		}

		if (resp.status >= 200 && resp.status < 300) {
			return parseJson<T>(resp);
		}

		const detail = extractDetail(resp);

		if (resp.status === 401) {
			this.authBlockedUntil = Date.now() + AUTH_BLOCK_MS;
			this.opts.onAuthError?.();
			throw new AuthError(detail || "Unauthorized");
		}

		if (resp.status >= 500 || resp.status === 429) {
			throw new TransientError(resp.status, detail || `HTTP ${resp.status}`);
		}

		if (resp.status === 404 && extractCode(resp) === "VAULT_NOT_REGISTERED") {
			throw new VaultNotRegisteredError(detail || "Vault not registered yet");
		}

		throw new PermanentError(resp.status, detail || `HTTP ${resp.status}`);
	}
}

function parseJson<T>(resp: RequestUrlResponse): T {
	// Plugin endpoints always return JSON; non-JSON 2xx is usually a
	// captive portal or CDN page — surface as transient so we back off.
	const text = resp.text ?? "";
	try {
		return JSON.parse(text) as T;
	} catch {
		throw new TransientError(
			resp.status,
			`Invalid JSON from server (got: ${text.slice(0, 80)})`
		);
	}
}

function safeJson(resp: RequestUrlResponse): Record<string, unknown> {
	try {
		return resp.text ? (JSON.parse(resp.text) as Record<string, unknown>) : {};
	} catch {
		return {};
	}
}

function extractDetail(resp: RequestUrlResponse): string {
	const json = safeJson(resp);
	if (typeof json.detail === "string") return json.detail;
	if (typeof json.message === "string") return json.message;
	const detailObj = json.detail;
	if (detailObj && typeof detailObj === "object") {
		const obj = detailObj as Record<string, unknown>;
		if (typeof obj.message === "string") return obj.message;
	}
	return resp.text?.slice(0, 200) ?? "";
}

function extractCode(resp: RequestUrlResponse): string | undefined {
	const json = safeJson(resp);
	const detailObj = json.detail;
	if (detailObj && typeof detailObj === "object") {
		const code = (detailObj as Record<string, unknown>).code;
		if (typeof code === "string") return code;
	}
	return undefined;
}
