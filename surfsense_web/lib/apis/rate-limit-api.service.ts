/**
 * Rate Limiting API Service
 *
 * Provides methods for interacting with the rate limiting management API.
 */

import type {
	BlockedIPsListResponse,
	UnlockIPRequest,
	UnlockResponse,
	BulkUnlockRequest,
	BulkUnlockResponse,
	RateLimitStatistics,
} from "@/contracts/types/rate-limit.types";
import { baseApiService } from "./base-api.service";

export class RateLimitApiService {
	/**
	 * Get list of currently blocked IP addresses
	 */
	getBlockedIPs = async (): Promise<BlockedIPsListResponse> => {
		return baseApiService.get(`/api/v1/rate-limiting/blocked-ips`);
	};

	/**
	 * Unlock a single IP address
	 */
	unlockIP = async (ipAddress: string, request?: UnlockIPRequest): Promise<UnlockResponse> => {
		return baseApiService.post(`/api/v1/rate-limiting/unlock/${ipAddress}`, undefined, {
			body: JSON.stringify(request || {}),
		});
	};

	/**
	 * Unlock multiple IP addresses at once
	 */
	bulkUnlockIPs = async (request: BulkUnlockRequest): Promise<BulkUnlockResponse> => {
		return baseApiService.post(`/api/v1/rate-limiting/bulk-unlock`, undefined, {
			body: JSON.stringify(request),
		});
	};

	/**
	 * Get rate limiting statistics
	 */
	getStats = async (): Promise<RateLimitStatistics> => {
		return baseApiService.get(`/api/v1/rate-limiting/stats`);
	};
}

export const rateLimitApiService = new RateLimitApiService();
