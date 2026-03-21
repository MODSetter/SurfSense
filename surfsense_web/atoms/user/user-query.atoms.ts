import { atomWithQuery } from "jotai-tanstack-query";
import { userApiService } from "@/lib/apis/user-api.service";
import { getBearerToken, isPublicRoute } from "@/lib/auth-utils";

export const USER_QUERY_KEY = ["user", "me"] as const;
const userQueryFn = () => userApiService.getMe();

export const currentUserAtom = atomWithQuery(() => {
	const pathname = typeof window !== "undefined" ? window.location.pathname : null;
	return {
		queryKey: USER_QUERY_KEY,
		staleTime: 5 * 60 * 1000,
		enabled: !!getBearerToken() && pathname !== null && !isPublicRoute(pathname),
		queryFn: userQueryFn,
	};
});
