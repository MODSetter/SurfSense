/**
 * One-time read-migration for persisted tabs: legacy state stored the workspace
 * as `searchSpaceId`. Map it to `workspaceId` on read so already-open tabs keep
 * their workspace association after the rename. Pure + dependency-free so it can
 * be unit-checked without loading the atom module.
 */
export function migrateLegacyTabs<T extends { tabs: Array<{ workspaceId?: number }> }>(
	state: T
): T {
	return {
		...state,
		tabs: state.tabs.map((t) => {
			const legacy = t as { workspaceId?: number; searchSpaceId?: number };
			return legacy.workspaceId === undefined && legacy.searchSpaceId !== undefined
				? { ...t, workspaceId: legacy.searchSpaceId }
				: t;
		}),
	};
}
