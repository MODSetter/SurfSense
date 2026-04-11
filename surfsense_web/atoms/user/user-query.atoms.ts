import { atomWithQuery } from "jotai-tanstack-query";
import { userApiService } from "@/lib/apis/user-api.service";

export const USER_QUERY_KEY = ["user", "me"] as const;
const userQueryFn = () => userApiService.getMe();

export const currentUserAtom = atomWithQuery(() => {
	return {
		queryKey: USER_QUERY_KEY,
		staleTime: 5 * 60 * 1000,
		enabled: true,
		queryFn: userQueryFn,
	};
});
