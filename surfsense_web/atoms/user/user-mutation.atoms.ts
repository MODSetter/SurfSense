import { atomWithMutation, queryClientAtom } from "jotai-tanstack-query";
import type { UpdateUserRequest } from "@/contracts/types/user.types";
import { userApiService } from "@/lib/apis/user-api.service";
import { USER_QUERY_KEY } from "./user-query.atoms";

export const updateUserMutationAtom = atomWithMutation((get) => {
	const queryClient = get(queryClientAtom);

	return {
		mutationKey: USER_QUERY_KEY,
		mutationFn: async (request: UpdateUserRequest) => {
			return userApiService.updateMe(request);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
		},
	};
});
