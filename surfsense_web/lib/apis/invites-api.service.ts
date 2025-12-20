import {
	type AcceptInviteRequest,
	type AcceptInviteResponse,
	acceptInviteRequest,
	acceptInviteResponse,
	type CreateInviteRequest,
	type CreateInviteResponse,
	createInviteRequest,
	createInviteResponse,
	type DeleteInviteRequest,
	type DeleteInviteResponse,
	deleteInviteRequest,
	deleteInviteResponse,
	type GetInviteInfoRequest,
	type GetInviteInfoResponse,
	type GetInvitesRequest,
	type GetInvitesResponse,
	getInviteInfoRequest,
	getInviteInfoResponse,
	getInvitesRequest,
	getInvitesResponse,
	type UpdateInviteRequest,
	type UpdateInviteResponse,
	updateInviteRequest,
	updateInviteResponse,
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
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

	/**
	 * Delete an invite
	 */
	deleteInvite = async (request: DeleteInviteRequest) => {
		const parsedRequest = deleteInviteRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/invites/${parsedRequest.data.invite_id}`,
			deleteInviteResponse
		);
	};

	/**
	 * Get invite info by invite code
	 */
	getInviteInfo = async (request: GetInviteInfoRequest) => {
		const parsedRequest = getInviteInfoRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/invites/${parsedRequest.data.invite_code}/info`,
			getInviteInfoResponse
		);
	};

	/**
	 * Accept an invite
	 */
	acceptInvite = async (request: AcceptInviteRequest) => {
		const parsedRequest = acceptInviteRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/invites/accept`, acceptInviteResponse, {
			body: parsedRequest.data,
		});
	};
}

export const invitesApiService = new InvitesApiService();
