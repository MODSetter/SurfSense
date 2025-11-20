import { atomWithMutation } from "jotai-tanstack-query";
import type { Verify2FARequest } from "@/contracts/types/auth.types";
import { authApiService } from "@/lib/apis/auth-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const verify2FAMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: cacheKeys.auth.user,
		mutationFn: async (request: Verify2FARequest) => {
			return authApiService.verify2FA(request);
		},
	};
});
