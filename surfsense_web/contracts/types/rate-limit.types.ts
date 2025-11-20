/**
 * Rate limiting and IP blocking types for the frontend.
 */

export interface BlockedIP {
	ip_address: string;
	user_id: string | null;
	username: string | null;
	blocked_at: string;
	expires_at: string;
	remaining_seconds: number;
	failed_attempts: number;
	reason: string;
	lockout_type: string;
}

export interface RateLimitStatistics {
	active_blocks: number;
	blocks_24h: number;
	blocks_7d: number;
	avg_lockout_duration: number;
}

export interface BlockedIPsListResponse {
	blocked_ips: BlockedIP[];
	total_count: number;
	statistics: RateLimitStatistics;
}

export interface UnlockIPRequest {
	reason?: string;
}

export interface UnlockResponse {
	success: boolean;
	message: string;
	ip_address?: string;
}

export interface BulkUnlockRequest {
	ip_addresses: string[];
	reason?: string;
}

export interface BulkUnlockResponse {
	success: boolean;
	unlocked_count: number;
	failed: string[];
	message: string;
}
