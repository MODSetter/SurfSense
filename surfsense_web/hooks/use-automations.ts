"use client";
import { useAtomValue } from "jotai";
import { automationsListAtom } from "@/atoms/automations/automations-query.atoms";

/**
 * List automations in the active workspace (first page).
 * Pagination knobs live in detail/list hooks below; v1 surfaces only the
 * first page since automation counts are expected to be small.
 */
export function useAutomations() {
	const { data, isLoading, error, refetch } = useAutomationsRaw();
	return {
		automations: data?.items ?? [],
		total: data?.total ?? 0,
		loading: isLoading,
		error,
		refresh: refetch,
	};
}

// Exposed for callers that prefer the raw react-query result shape.
export function useAutomationsRaw() {
	return useAtomValue(automationsListAtom);
}
