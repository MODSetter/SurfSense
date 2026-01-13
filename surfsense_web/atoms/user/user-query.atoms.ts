import { atomWithQuery } from "jotai-tanstack-query";
import { userApiService } from "@/lib/apis/user-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const currentUserAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.user.current(),
		staleTime: 5 * 60 * 1000, // 5 minutes
		// Only fetch user data when a bearer token is present
		enabled: !!getBearerToken(),
		queryFn: async () => {
			return userApiService.getMe();
		},
	};
});
