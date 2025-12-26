import {
	type DeleteMembershipRequest,
	type DeleteMembershipResponse,
	deleteMembershipRequest,
	deleteMembershipResponse,
	type GetMembersRequest,
	type GetMembersResponse,
	type GetMyAccessRequest,
	type GetMyAccessResponse,
	getMembersRequest,
	getMembersResponse,
	getMyAccessRequest,
	getMyAccessResponse,
	type LeaveSearchSpaceRequest,
	type LeaveSearchSpaceResponse,
	leaveSearchSpaceRequest,
	leaveSearchSpaceResponse,
	type UpdateMembershipRequest,
	type UpdateMembershipResponse,
	updateMembershipRequest,
	updateMembershipResponse,
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/members`,
			getMembersResponse
		);
	};

	/**
	 * Update a member's role
	 */
	updateMember = async (request: UpdateMembershipRequest) => {
		const parsedRequest = updateMembershipRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/members/${parsedRequest.data.membership_id}`,
			updateMembershipResponse,
			{
				body: parsedRequest.data.data,
			}
		);
	};

	/**
	 * Delete a member from search space
	 */
	deleteMember = async (request: DeleteMembershipRequest) => {
		const parsedRequest = deleteMembershipRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/members/${parsedRequest.data.membership_id}`,
			deleteMembershipResponse
		);
	};

	/**
	 * Leave a search space (remove self)
	 */
	leaveSearchSpace = async (request: LeaveSearchSpaceRequest) => {
		const parsedRequest = leaveSearchSpaceRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/members/me`,
			leaveSearchSpaceResponse
		);
	};

	/**
	 * Get current user's access information for a search space
	 */
	getMyAccess = async (request: GetMyAccessRequest) => {
		const parsedRequest = getMyAccessRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/my-access`,
			getMyAccessResponse
		);
	};
}

export const membersApiService = new MembersApiService();
