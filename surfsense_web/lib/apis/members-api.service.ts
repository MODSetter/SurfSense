import { baseApiService } from "./base-api.service";
import {
	type GetMembersRequest,
	getMembersRequest,
	getMembersResponse,
	type UpdateMembershipRequest,
	updateMembershipRequest,
	updateMembershipResponse,
} from "@/contracts/types/members.types";

class MembersApiService {
	/**
	 * Get members of a search space
	 */
	async getMembers(request: GetMembersRequest) {
		const parsedRequest = getMembersRequest.parse(request);
		return baseApiService.get(
			`/searchspaces/${parsedRequest.search_space_id}/members`,
			getMembersResponse,
		);
	}

	/**
	 * Update a member's role
	 */
	async updateMember(request: UpdateMembershipRequest) {
		const parsedRequest = updateMembershipRequest.parse(request);
		return baseApiService.put(
			`/searchspaces/${parsedRequest.search_space_id}/members/${parsedRequest.membership_id}`,
			updateMembershipResponse,
			{
				body: parsedRequest.data,
			},
		);
	}
}

export const membersApiService = new MembersApiService();
