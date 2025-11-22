"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AUTH_TOKEN_KEY } from "@/lib/constants";
import { handleSessionExpired } from "@/lib/auth-utils";

interface User {
	id: string;
	email: string;
	is_active: boolean;
	is_superuser: boolean;
	is_verified: boolean;
	pages_limit: number;
	pages_used: number;
}

interface AuthState {
	user: User | null;
	isLoading: boolean;
	isAuthenticated: boolean;
	error: string | null;
}

/**
 * Enhanced authentication hook that verifies tokens with the backend
 * and provides user session state
 *
 * @param requireSuperuser - If true, will redirect non-superuser users to dashboard
 * @returns Authentication state including user data, loading state, and error
 */
export function useAuth(requireSuperuser = false): AuthState {
	const router = useRouter();
	const [state, setState] = useState<AuthState>({
		user: null,
		isLoading: true,
		isAuthenticated: false,
		error: null,
	});

	useEffect(() => {
		const MAX_RETRIES = 2;
		const BASE_DELAY_MS = 1000;

		const verifyAuth = async (retryCount = 0) => {

			try {
				// Only run on client-side
				if (typeof window === "undefined") return;

				const token = localStorage.getItem(AUTH_TOKEN_KEY);

				// No token - redirect to login
				if (!token) {
					router.push("/login");
					return;
				}

				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

				// Verify token with backend
				const response = await fetch(`${backendUrl}/verify-token`, {
					method: "GET",
					credentials: "include",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
				});

				// Token is invalid or expired
				if (response.status === 401) {
					toast.error("Session Expired", {
						description: "Your session has expired. Please log in again.",
						duration: 3000,
					});
					handleSessionExpired();
					return;
				}

				if (!response.ok) {
					throw new Error(`Authentication failed: ${response.status}`);
				}

				const data = await response.json();

				// Validate response structure
				if (!data || !data.user || typeof data.user !== "object") {
					console.error("Invalid response from verify-token endpoint");
					toast.error("Authentication Error", {
						description: "Unable to verify your session. Please log in again.",
						duration: 5000,
					});
					handleSessionExpired();
					return;
				}

				const user = data.user as User;

				// Check superuser requirement
				if (requireSuperuser && !user.is_superuser) {
					toast.error("Access Denied", {
						description: "You must be an administrator to access this page.",
						duration: 5000,
					});
					router.push("/dashboard");
					return;
				}

				// Success - user is authenticated
				setState({
					user,
					isLoading: false,
					isAuthenticated: true,
					error: null,
				});

			} catch (error: any) {
				console.error("Error verifying authentication:", error);

				// Retry on network errors (but not on 401)
				if (retryCount < MAX_RETRIES && error.message !== "Session expired") {
					console.log(`Retrying authentication verification (${retryCount + 1}/${MAX_RETRIES})...`);
					// Exponential backoff with proportional jitter to prevent thundering herd
					const baseBackoff = Math.pow(2, retryCount) * BASE_DELAY_MS;
					const jitter = Math.random() * (baseBackoff / 2);
					const backoffMs = baseBackoff + jitter;
					setTimeout(() => verifyAuth(retryCount + 1), backoffMs);
					return;
				}

				setState({
					user: null,
					isLoading: false,
					isAuthenticated: false,
					error: error.message || "Authentication failed",
				});

				toast.error("Authentication Error", {
					description: "Unable to verify authentication. Please log in again.",
					duration: 3000,
				});

				// Clear invalid token and redirect
				handleSessionExpired();
			}
		};

		verifyAuth();
	}, [router, requireSuperuser]);

	return state;
}
