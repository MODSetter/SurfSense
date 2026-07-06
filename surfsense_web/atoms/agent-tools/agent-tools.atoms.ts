import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import { agentToolsApiService } from "@/lib/apis/agent-tools-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeWorkspaceIdAtom } from "../workspaces/workspace-query.atoms";

export const agentToolsAtom = atomWithQuery((_get) => ({
	queryKey: cacheKeys.agentTools.all(),
	staleTime: 30 * 60 * 1000, // 30 min – tool list rarely changes
	queryFn: async () => agentToolsApiService.getTools(),
}));

const STORAGE_PREFIX = "surfsense-disabled-tools-";

function loadDisabledTools(workspaceId: string): string[] {
	if (typeof window === "undefined") return [];
	try {
		const raw = localStorage.getItem(`${STORAGE_PREFIX}${workspaceId}`);
		return raw ? (JSON.parse(raw) as string[]) : [];
	} catch {
		return [];
	}
}

function saveDisabledTools(workspaceId: string, tools: string[]) {
	if (typeof window === "undefined") return;
	if (tools.length === 0) {
		localStorage.removeItem(`${STORAGE_PREFIX}${workspaceId}`);
	} else {
		localStorage.setItem(`${STORAGE_PREFIX}${workspaceId}`, JSON.stringify(tools));
	}
}

const disabledToolsBaseAtom = atom<string[]>([]);

/** Tracks whether the atom has been hydrated from localStorage for the current workspace */
const hydratedForAtom = atom<string | null>(null);

/**
 * Read/write atom for the set of disabled tool names.
 * Persists to localStorage keyed by workspace ID.
 */
export const disabledToolsAtom = atom(
	(get) => {
		const workspaceId = get(activeWorkspaceIdAtom);
		const hydratedFor = get(hydratedForAtom);
		if (workspaceId && hydratedFor !== workspaceId) {
			return loadDisabledTools(workspaceId);
		}
		return get(disabledToolsBaseAtom);
	},
	(get, set, update: string[] | ((prev: string[]) => string[])) => {
		const workspaceId = get(activeWorkspaceIdAtom);
		const prev = get(disabledToolsBaseAtom);
		const next = typeof update === "function" ? update(prev) : update;
		set(disabledToolsBaseAtom, next);
		set(hydratedForAtom, workspaceId);
		if (workspaceId) {
			saveDisabledTools(workspaceId, next);
		}
	}
);

/**
 * Hydrate disabled tools from localStorage when workspace changes.
 * Call this from a useEffect in a component that has access to the workspace.
 */
export const hydrateDisabledToolsAtom = atom(null, (get, set) => {
	const workspaceId = get(activeWorkspaceIdAtom);
	if (!workspaceId) return;
	const stored = loadDisabledTools(workspaceId);
	set(disabledToolsBaseAtom, stored);
	set(hydratedForAtom, workspaceId);
});

/** Toggle a single tool's enabled/disabled state */
export const toggleToolAtom = atom(null, (get, set, toolName: string) => {
	const workspaceId = get(activeWorkspaceIdAtom);
	const current = get(disabledToolsBaseAtom);
	const next = current.includes(toolName)
		? current.filter((t) => t !== toolName)
		: [...current, toolName];
	set(disabledToolsBaseAtom, next);
	set(hydratedForAtom, workspaceId);
	if (workspaceId) {
		saveDisabledTools(workspaceId, next);
	}
});

/** Derive the count of currently enabled tools */
export const enabledToolCountAtom = atom((get) => {
	const { data: tools } = get(agentToolsAtom);
	const disabled = get(disabledToolsAtom);
	if (!tools) return 0;
	return tools.length - disabled.filter((d) => tools.some((t) => t.name === d)).length;
});
