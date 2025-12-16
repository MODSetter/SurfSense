import { atomWithQuery } from "jotai-tanstack-query";
import { userApiService } from "@/lib/apis/user-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const currentUserAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.user.current(),
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return userApiService.getMe();
		},
	};
});
