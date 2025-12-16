import {
	type CreateInviteRequest,
	type CreateInviteResponse,
	type GetInvitesRequest,
	type GetInvitesResponse,
	type UpdateInviteRequest,
	type UpdateInviteResponse,
	type DeleteInviteRequest,
	type DeleteInviteResponse,
	type GetInviteInfoRequest,
	type GetInviteInfoResponse,
	type AcceptInviteRequest,
	type AcceptInviteResponse,
	createInviteRequest,
	createInviteResponse,
	getInvitesRequest,
	getInvitesResponse,
	updateInviteRequest,
	updateInviteResponse,
	deleteInviteRequest,
	deleteInviteResponse,
	getInviteInfoRequest,
	getInviteInfoResponse,
	acceptInviteRequest,
	acceptInviteResponse,
} from "@/contracts/types/invites.types";
import { ValidationError } from "@/lib/error";
import { baseApiService } from "./base-api.service";

class InvitesApiService {
	/**
	 * Create a new invite
	 */
	createInvite = async (request: CreateInviteRequest) => {
		const parsedRequest = createInviteRequest.safeParse(request);
		
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/invites`,
			createInviteResponse,
			{
				body: parsedRequest.data.data,
			}
		);
	};

	/**
	 * Get all invites for a search space
	 */
	getInvites = async (request: GetInvitesRequest) => {
		const parsedRequest = getInvitesRequest.safeParse(request);
		
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
		`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/invites`,
		getInvitesResponse
	);
	};

	/**
	 * Update an invite
	 */
	updateInvite = async (request: UpdateInviteRequest) => {
		const parsedRequest = updateInviteRequest.safeParse(request);
		
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/invites/${parsedRequest.data.invite_id}`,
			updateInviteResponse,
			{
				body: parsedRequest.data.data,
			}
		);
	};
}

export const invitesApiService = new InvitesApiService();
