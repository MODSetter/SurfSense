import { getBearerToken } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";
import { DEFAULT_DURATION, MAX_DURATION, MIN_DURATION } from "./types";

export async function fetchCode(
	searchSpaceId: number,
	topic: string,
	sourceContent: string,
	attempt: number,
	error?: string,
	signal?: AbortSignal
): Promise<string> {
	const token = getBearerToken();
	const res = await fetch(`${BACKEND_URL}/api/v1/video/generate-code`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token || ""}`,
		},
		body: JSON.stringify({
			search_space_id: searchSpaceId,
			topic,
			source_content: sourceContent,
			attempt,
			error: error ?? null,
		}),
		signal,
	});

	if (!res.ok) {
		const detail = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(detail.detail || `HTTP ${res.status}`);
	}

	const data = await res.json();
	if (typeof data.code !== "string" || !data.code) {
		throw new Error("Invalid response from server: missing code field");
	}
	return data.code;
}

export function extractDuration(code: string): number {
	const match = code.match(/\bTOTAL_DURATION\s*=\s*(\d+)/);
	if (!match) return DEFAULT_DURATION;
	const n = parseInt(match[1], 10);
	return Math.min(MAX_DURATION, Math.max(MIN_DURATION, n));
}
