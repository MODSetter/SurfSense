import {
	type CreatePatRequest,
	createPatRequest,
	createPatResponse,
	deletePatResponse,
	listPatsResponse,
} from "@/contracts/types/pat.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class PatsApiService {
	listPats = async () => {
		return baseApiService.get("/api/v1/pats", listPatsResponse);
	};

	createPat = async (request: CreatePatRequest) => {
		const parsedRequest = createPatRequest.safeParse(request);
		if (!parsedRequest.success) {
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post("/api/v1/pats", createPatResponse, {
			body: parsedRequest.data,
		});
	};

	deletePat = async (id: number) => {
		return baseApiService.delete(`/api/v1/pats/${id}`, deletePatResponse);
	};
}

export const patsApiService = new PatsApiService();
