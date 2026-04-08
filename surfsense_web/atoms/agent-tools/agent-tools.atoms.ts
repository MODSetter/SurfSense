import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import { type AgentToolInfo, agentToolsApiService } from "@/lib/apis/agent-tools-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const agentToolsAtom = atomWithQuery((_get) => ({
	queryKey: cacheKeys.agentTools.all(),
	staleTime: 30 * 60 * 1000, // 30 min – tool list rarely changes
	queryFn: async () => agentToolsApiService.getTools(),
}));

const STORAGE_PREFIX = "surfsense-disabled-tools-";

function loadDisabledTools(searchSpaceId: string): string[] {
	if (typeof window === "undefined") return [];
	try {
		const raw = localStorage.getItem(`${STORAGE_PREFIX}${searchSpaceId}`);
		return raw ? (JSON.parse(raw) as string[]) : [];
	} catch {
		return [];
	}
}

function saveDisabledTools(searchSpaceId: string, tools: string[]) {
	if (typeof window === "undefined") return;
	if (tools.length === 0) {
		localStorage.removeItem(`${STORAGE_PREFIX}${searchSpaceId}`);
	} else {
		localStorage.setItem(`${STORAGE_PREFIX}${searchSpaceId}`, JSON.stringify(tools));
	}
}

const disabledToolsBaseAtom = atom<string[]>([]);

/** Tracks whether the atom has been hydrated from localStorage for the current search space */
const hydratedForAtom = atom<string | null>(null);

/**
 * Read/write atom for the set of disabled tool names.
 * Persists to localStorage keyed by search space ID.
 */
export const disabledToolsAtom = atom(
	(get) => {
		const searchSpaceId = get(activeSearchSpaceIdAtom);
		const hydratedFor = get(hydratedForAtom);
		if (searchSpaceId && hydratedFor !== searchSpaceId) {
			return loadDisabledTools(searchSpaceId);
		}
		return get(disabledToolsBaseAtom);
	},
	(get, set, update: string[] | ((prev: string[]) => string[])) => {
		const searchSpaceId = get(activeSearchSpaceIdAtom);
		const prev = get(disabledToolsBaseAtom);
		const next = typeof update === "function" ? update(prev) : update;
		set(disabledToolsBaseAtom, next);
		set(hydratedForAtom, searchSpaceId);
		if (searchSpaceId) {
			saveDisabledTools(searchSpaceId, next);
		}
	}
);

/**
 * Hydrate disabled tools from localStorage when search space changes.
 * Call this from a useEffect in a component that has access to the search space.
 */
export const hydrateDisabledToolsAtom = atom(null, (get, set) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	if (!searchSpaceId) return;
	const stored = loadDisabledTools(searchSpaceId);
	set(disabledToolsBaseAtom, stored);
	set(hydratedForAtom, searchSpaceId);
});

/** Toggle a single tool's enabled/disabled state */
export const toggleToolAtom = atom(null, (get, set, toolName: string) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const current = get(disabledToolsBaseAtom);
	const next = current.includes(toolName)
		? current.filter((t) => t !== toolName)
		: [...current, toolName];
	set(disabledToolsBaseAtom, next);
	set(hydratedForAtom, searchSpaceId);
	if (searchSpaceId) {
		saveDisabledTools(searchSpaceId, next);
	}
});

/** Derive the count of currently enabled tools */
export const enabledToolCountAtom = atom((get) => {
	const { data: tools } = get(agentToolsAtom);
	const disabled = get(disabledToolsAtom);
	if (!tools) return 0;
	return tools.length - disabled.filter((d) => tools.some((t) => t.name === d)).length;
});
