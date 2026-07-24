"use client";
import { useQuery } from "@tanstack/react-query";
import type { ScraperCapability } from "@/contracts/types/scraper.types";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/**
 * The platform-native verb registry only changes on deploy, so it is cached
 * aggressively. Returns every verb with its input JSON schema for the form.
 */
export function useScraperCapabilities(workspaceId: number | string) {
	return useQuery<ScraperCapability[], Error>({
		queryKey: cacheKeys.scrapers.capabilities(workspaceId),
		queryFn: () => scrapersApiService.listCapabilities(workspaceId),
		staleTime: 60 * 60 * 1000,
		gcTime: 60 * 60 * 1000,
	});
}
