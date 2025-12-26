import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	DeleteMembershipRequest,
	DeleteMembershipResponse,
	LeaveSearchSpaceRequest,
	LeaveSearchSpaceResponse,
	UpdateMembershipRequest,
	UpdateMembershipResponse,
} from "@/contracts/types/members.types";
import { membersApiService } from "@/lib/apis/members-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const updateMemberMutationAtom = atomWithMutation(() => {
	return {
		mutationFn: async (request: UpdateMembershipRequest) => {
			return membersApiService.updateMember(request);
		},
		onSuccess: (_: UpdateMembershipResponse, request: UpdateMembershipRequest) => {
			toast.success("Member updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.all(request.search_space_id.toString()),
			});
		},
		onError: () => {
			toast.error("Failed to update member");
		},
	};
});

export const deleteMemberMutationAtom = atomWithMutation(() => {
	return {
		mutationFn: async (request: DeleteMembershipRequest) => {
			return membersApiService.deleteMember(request);
		},
		onSuccess: (_: DeleteMembershipResponse, request: DeleteMembershipRequest) => {
			toast.success("Member removed successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.all(request.search_space_id.toString()),
			});
		},
		onError: () => {
			toast.error("Failed to remove member");
		},
	};
});

export const leaveSearchSpaceMutationAtom = atomWithMutation(() => {
	return {
		mutationFn: async (request: LeaveSearchSpaceRequest) => {
			return membersApiService.leaveSearchSpace(request);
		},
		onSuccess: (_: LeaveSearchSpaceResponse, request: LeaveSearchSpaceRequest) => {
			toast.success("Successfully left the search space");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.members.all(request.search_space_id.toString()),
			});
		},
		onError: () => {
			toast.error("Failed to leave search space");
		},
	};
});
