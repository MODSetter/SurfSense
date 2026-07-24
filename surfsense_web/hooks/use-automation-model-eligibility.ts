"use client";
import { useQuery } from "@tanstack/react-query";
import type { ModelEligibility } from "@/contracts/types/automation.types";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/**
 * Whether the workspace's configured models are billable for automations.
 *
 * Automations may only run on premium global models or user-provided (BYOK)
 * models; free global models and Auto mode are blocked so every run is metered
 * in premium credits. Creation surfaces use this to gate their CTAs before the
 * user invests effort drafting an automation that can't be saved.
 *
 * Keyed by workspace id (not the jotai "current scope" atom) so it can be
 * used on the create route as well as the list page.
 */
export function useAutomationModelEligibility(workspaceId: number | undefined) {
	return useQuery<ModelEligibility, Error>({
		queryKey: cacheKeys.automations.modelEligibility(workspaceId ?? 0),
		queryFn: () => automationsApiService.getModelEligibility(workspaceId as number),
		enabled: !!workspaceId,
		staleTime: 60_000,
	});
}
