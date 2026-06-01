"use client";
import { useQuery } from "@tanstack/react-query";
import type { Automation } from "@/contracts/types/automation.types";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/**
 * Fetch a single automation with its definition and triggers.
 * Lives outside the jotai atom layer because it's keyed by id, not by the
 * "current scope" the atom layer assumes.
 */
export function useAutomation(automationId: number | undefined) {
	return useQuery<Automation, Error>({
		queryKey: cacheKeys.automations.detail(automationId ?? 0),
		queryFn: () => automationsApiService.getAutomation(automationId as number),
		enabled: !!automationId,
		staleTime: 60_000,
	});
}
