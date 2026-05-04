import { atomWithQuery } from "jotai-tanstack-query";
import { userApiService } from "@/lib/apis/user-api.service";
import { getBearerToken } from "@/lib/auth-utils";

export const USER_QUERY_KEY = ["user", "me"] as const;
const userQueryFn = () => userApiService.getMe();

export const currentUserAtom = atomWithQuery(() => {
	return {
		queryKey: USER_QUERY_KEY,
		// Live-changing numeric fields (pages_*, premium_credit_micros_*)
		// are now pushed via Zero (queries.user.me()), so /users/me only
		// needs to fire once per session for the static profile fields.
		staleTime: Infinity,
		enabled: !!getBearerToken(),
		queryFn: userQueryFn,
	};
});
