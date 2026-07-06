import { atomWithQuery } from "jotai-tanstack-query";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { membersApiService } from "@/lib/apis/members-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const membersAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.members.all(searchSpaceId?.toString() ?? ""),
		enabled: !!searchSpaceId,
		staleTime: 3 * 1000, // 3 seconds - short staleness for live collaboration
		refetchInterval: 2 * 60 * 1000, // 2 minutes
		queryFn: async () => {
			if (!searchSpaceId) {
				return [];
			}
			return membersApiService.getMembers({
				workspace_id: Number(searchSpaceId),
			});
		},
	};
});

export const myAccessAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeWorkspaceIdAtom);

	return {
		queryKey: cacheKeys.members.myAccess(searchSpaceId?.toString() ?? ""),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			if (!searchSpaceId) {
				return null;
			}
			return membersApiService.getMyAccess({
				workspace_id: Number(searchSpaceId),
			});
		},
	};
});

/**
 * Helper function to check if the current user has a specific permission.
 *
 * @param access - The access object from useAtomValue(myAccessAtom)
 * @param permission - The permission string to check
 * @returns boolean indicating if the user has the permission
 *
 * @example
 * const access = useAtomValue(myAccessAtom);
 * if (canPerform(access, 'manage_members')) { ... }
 */
export function canPerform(
	access: { is_owner: boolean; permissions?: string[] } | null | undefined,
	permission: string
): boolean {
	if (!access) return false;
	if (access.is_owner) return true;
	return access.permissions?.includes(permission) ?? false;
}

/**
 * Hook wrapper for canPerform that reads from myAccessAtom internally.
 * Use this if you want to avoid calling useAtomValue(myAccessAtom) separately.
 *
 * @param permission - The permission string to check
 * @returns boolean indicating if the user has the permission
 *
 * @example
 * const canManageMembers = usePermissionGate('manage_members');
 */
export function usePermissionGate(permission: string): boolean {
	const access = useAtomValue(myAccessAtom);
	return canPerform(access, permission);
}
