import { atomWithMutation } from "jotai-tanstack-query";
import type { LoginRequest, RegisterRequest } from "@/contracts/types/auth.types";
import { authApiService } from "@/lib/apis/auth-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const registerMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: cacheKeys.auth.user,
		mutationFn: async (request: RegisterRequest) => {
			return authApiService.register(request);
		},
	};
});

export const loginMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: cacheKeys.auth.user,
		mutationFn: async (request: LoginRequest) => {
			return authApiService.login(request);
		},
	};
});
