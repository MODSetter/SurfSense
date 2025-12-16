import {
	type GetMembersRequest,
	type GetMembersResponse,
	type UpdateMembershipRequest,
	type UpdateMembershipResponse,
	type DeleteMembershipRequest,
	type DeleteMembershipResponse,
	type LeaveSearchSpaceRequest,
	type LeaveSearchSpaceResponse,
	getMembersRequest,
	getMembersResponse,
	updateMembershipRequest,
	updateMembershipResponse,
	deleteMembershipRequest,
	deleteMembershipResponse,
	leaveSearchSpaceRequest,
	leaveSearchSpaceResponse,
} from "@/contracts/types/members.types";
import { ValidationError } from "@/lib/error";
import { baseApiService } from "./base-api.service";

class MembersApiService {
	/**
	 * Get members of a search space
	 */
	getMembers = async (request: GetMembersRequest) => {
		const parsedRequest = getMembersRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/searchspaces/${parsedRequest.data.search_space_id}/members`,
			getMembersResponse,
		);
	};

	/**
	 * Update a member's role
	 */
	updateMember = async (request: UpdateMembershipRequest) => {
		const parsedRequest = updateMembershipRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/searchspaces/${parsedRequest.data.search_space_id}/members/${parsedRequest.data.membership_id}`,
			updateMembershipResponse,
			{
				body: parsedRequest.data.data,
			},
		);
	};

	/**
	 * Delete a member from search space
	 */
	deleteMember = async (request: DeleteMembershipRequest) => {
		const parsedRequest = deleteMembershipRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/searchspaces/${parsedRequest.data.search_space_id}/members/${parsedRequest.data.membership_id}`,
			deleteMembershipResponse,
		);
	};

	/**
	 * Leave a search space (remove self)
	 */
	leaveSearchSpace = async (request: LeaveSearchSpaceRequest) => {
		const parsedRequest = leaveSearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/searchspaces/${parsedRequest.data.search_space_id}/members/me`,
			leaveSearchSpaceResponse,
		);
	};
}

export const membersApiService = new MembersApiService();
