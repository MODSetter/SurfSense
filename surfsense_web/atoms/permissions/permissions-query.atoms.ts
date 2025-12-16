import { atomWithQuery } from "jotai-tanstack-query";
import { permissionsApiService } from "@/lib/apis/permissions-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const permissionsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.permissions.all(),
		staleTime: 10 * 60 * 1000, // 10 minutes
		queryFn: async () => {
			return permissionsApiService.getPermissions();
		},
	};
});
