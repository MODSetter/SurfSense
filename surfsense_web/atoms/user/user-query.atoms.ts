import { atomWithQuery } from "jotai-tanstack-query";
import { userApiService } from "@/lib/apis/user-api.service";
import { getBearerToken, isPublicRoute } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const currentUserAtom = atomWithQuery(() => {
	const pathname = typeof window !== "undefined" ? window.location.pathname : null;
	return {
		queryKey: cacheKeys.user.current(),
		staleTime: 5 * 60 * 1000, // 5 minutes
		enabled: !!getBearerToken() && pathname !== null && !isPublicRoute(pathname),
		queryFn: async () => userApiService.getMe(),
	};
});
