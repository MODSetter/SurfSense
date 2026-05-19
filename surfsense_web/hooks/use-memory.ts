"use client";

import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { baseApiService } from "@/lib/apis/base-api.service";

export const MEMORY_HARD_LIMIT = 25_000;

const MemoryReadSchema = z.object({
	memory_md: z.string(),
});

type MemoryScope = "user" | "team";

interface UseMemoryOptions {
	scope: MemoryScope;
	searchSpaceId?: number | null;
	autoLoad?: boolean;
}

function getMemoryPath(scope: MemoryScope, searchSpaceId?: number | null) {
	if (scope === "user") return "/api/v1/users/me/memory";
	if (!searchSpaceId) throw new Error("searchSpaceId is required for team memory");
	return `/api/v1/searchspaces/${searchSpaceId}/memory`;
}

export function stripMemoryDisplayPrefixes(memory: string) {
	return memory.replace(
		/^\s*-\s+(?:\(\d{4}-\d{2}-\d{2}\)\s*\[(?:fact|pref|instr)\]\s*|\d{4}-\d{2}-\d{2}:\s*)/gim,
		"- "
	);
}

export function useMemory({ scope, searchSpaceId, autoLoad = true }: UseMemoryOptions) {
	const [memory, setMemory] = useState("");
	const [loading, setLoading] = useState(autoLoad);
	const [saving, setSaving] = useState(false);

	const load = useCallback(async () => {
		setLoading(true);
		try {
			const data = await baseApiService.get(getMemoryPath(scope, searchSpaceId), MemoryReadSchema);
			setMemory(data.memory_md);
			return data.memory_md;
		} finally {
			setLoading(false);
		}
	}, [scope, searchSpaceId]);

	useEffect(() => {
		if (!autoLoad) return;
		load().catch(() => {
			setLoading(false);
		});
	}, [autoLoad, load]);

	const save = useCallback(
		async (memoryMd: string) => {
			setSaving(true);
			try {
				const data = await baseApiService.put(
					getMemoryPath(scope, searchSpaceId),
					MemoryReadSchema,
					{
						body: { memory_md: memoryMd },
					}
				);
				setMemory(data.memory_md);
				return data.memory_md;
			} finally {
				setSaving(false);
			}
		},
		[scope, searchSpaceId]
	);

	const reset = useCallback(async () => {
		setSaving(true);
		try {
			const data = await baseApiService.post(
				`${getMemoryPath(scope, searchSpaceId)}/reset`,
				MemoryReadSchema
			);
			setMemory(data.memory_md);
			return data.memory_md;
		} finally {
			setSaving(false);
		}
	}, [scope, searchSpaceId]);

	return {
		memory,
		setMemory,
		displayMemory: stripMemoryDisplayPrefixes(memory),
		loading,
		saving,
		load,
		save,
		reset,
	};
}

export function useUserMemory(searchSpaceId?: number | null) {
	return useMemory({ scope: "user", searchSpaceId });
}

export function useTeamMemory(searchSpaceId?: number | null) {
	return useMemory({ scope: "team", searchSpaceId });
}
