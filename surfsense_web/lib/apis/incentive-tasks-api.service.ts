import {
	type CompleteTaskResponse,
	completeTaskResponse,
	type GetIncentiveTasksResponse,
	getIncentiveTasksResponse,
	type IncentiveTaskTypeEnum,
} from "@/contracts/types/incentive-tasks.types";
import { baseApiService } from "./base-api.service";

class IncentiveTasksApiService {
	/**
	 * Get all available incentive tasks with completion status
	 */
	getTasks = async (): Promise<GetIncentiveTasksResponse> => {
		return baseApiService.get("/api/v1/incentive-tasks", getIncentiveTasksResponse);
	};

	/**
	 * Mark a task as completed and receive page reward
	 */
	completeTask = async (taskType: IncentiveTaskTypeEnum): Promise<CompleteTaskResponse> => {
		return baseApiService.post(
			`/api/v1/incentive-tasks/${taskType}/complete`,
			completeTaskResponse
		);
	};
}

export const incentiveTasksApiService = new IncentiveTasksApiService();
