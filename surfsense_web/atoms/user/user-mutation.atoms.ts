import { atomWithMutation, queryClientAtom } from "jotai-tanstack-query";
import type { UpdateUserRequest } from "@/contracts/types/user.types";
import { userApiService } from "@/lib/apis/user-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const updateUserMutationAtom = atomWithMutation((get) => {
	const queryClient = get(queryClientAtom);

	return {
		mutationKey: cacheKeys.user.current(),
		mutationFn: async (request: UpdateUserRequest) => {
			return userApiService.updateMe(request);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.user.current() });
		},
	};
});
