"use client";

import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

export type MemoryScope = "user" | "team";

export interface MemoryLimits {
	soft: number;
	hard: number;
}

export type MemoryLimitLevel = "ok" | "warning" | "error";

export interface MemoryEditorDocument {
	document_id: number;
	title: string;
	document_type: "USER_MEMORY" | "TEAM_MEMORY";
	source_markdown: string;
}

interface MemoryReadResponse {
	memory_md?: string;
	limits?: MemoryLimits;
}

function getMemoryPath(scope: MemoryScope, workspaceId?: number | null) {
	if (scope === "user") return "/api/v1/users/me/memory";
	if (!workspaceId) throw new Error("Missing workspace context");
	return `/api/v1/workspaces/${workspaceId}/memory`;
}

export function getMemoryLimitState(length: number, limits?: MemoryLimits | null) {
	if (!limits) {
		return {
			level: "ok" as MemoryLimitLevel,
			label: `${length.toLocaleString()} chars`,
			isOverLimit: false,
		};
	}

	const isOverLimit = length > limits.hard;
	const isNearLimit = length > limits.soft;
	const level: MemoryLimitLevel = isOverLimit ? "error" : isNearLimit ? "warning" : "ok";
	const suffix = isOverLimit ? " - Exceeds limit" : isNearLimit ? " - Approaching limit" : "";

	return {
		level,
		label: `${length.toLocaleString()}/${limits.hard.toLocaleString()} chars${suffix}`,
		isOverLimit,
	};
}

export async function fetchMemoryEditorDocument({
	scope,
	workspaceId,
	title,
	signal,
}: {
	scope: MemoryScope;
	workspaceId?: number | null;
	title?: string | null;
	signal?: AbortSignal;
}) {
	const response = await authenticatedFetch(buildBackendUrl(getMemoryPath(scope, workspaceId)), {
		method: "GET",
		signal,
	});
	if (!response.ok) {
		const errorData = await response.json().catch(() => ({ detail: "Failed to fetch memory" }));
		throw new Error(errorData.detail || "Failed to fetch memory");
	}

	const data = (await response.json()) as MemoryReadResponse;
	const isTeamMemory = scope === "team";

	return {
		limits: data.limits ?? null,
		document: {
			document_id: isTeamMemory ? -1002 : -1001,
			title: title || (isTeamMemory ? "Team Memory" : "Personal Memory"),
			document_type: isTeamMemory ? "TEAM_MEMORY" : "USER_MEMORY",
			source_markdown: data.memory_md ?? "",
		} satisfies MemoryEditorDocument,
	};
}

export async function saveMemoryMarkdown({
	scope,
	workspaceId,
	markdown,
}: {
	scope: MemoryScope;
	workspaceId?: number | null;
	markdown: string;
}) {
	const response = await authenticatedFetch(buildBackendUrl(getMemoryPath(scope, workspaceId)), {
		method: "PUT",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ memory_md: markdown }),
	});
	if (!response.ok) {
		const errorData = await response.json().catch(() => ({ detail: "Failed to save memory" }));
		throw new Error(errorData.detail || "Failed to save memory");
	}

	const data = (await response.json()) as MemoryReadResponse;

	return {
		markdown: data.memory_md ?? markdown,
		limits: data.limits,
	};
}
