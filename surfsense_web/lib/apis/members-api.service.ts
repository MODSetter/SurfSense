import { baseApiService } from "./base-api.service";
import {
	type GetMembersRequest,
	getMembersRequest,
	getMembersResponse,
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
}

export const membersApiService = new MembersApiService();
