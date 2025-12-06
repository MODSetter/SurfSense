"use client";

import { useEffect, useState } from "react";
import { logger } from "@/lib/logger";
import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-utils";

interface User {
	id: string;
	email: string;
	is_active: boolean;
	is_superuser: boolean;
	is_verified: boolean;
	pages_limit: number;
	pages_used: number;
}

export function useUser() {
	const [user, setUser] = useState<User | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchUser = async () => {
			try {
				// Only run on client-side
				if (typeof window === "undefined") return;

				setLoading(true);
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/users/me`,
					{ method: "GET" }
				);

				if (!response.ok) {
					throw new Error(`Failed to fetch user: ${response.status}`);
				}

				const data = await response.json();
				setUser(data);
				setError(null);
			} catch (err: any) {
				setError(err.message || "Failed to fetch user");
				logger.error("Error fetching user:", err);
			} finally {
				setLoading(false);
			}
		};

		fetchUser();
	}, []);

	return { user, loading, error };
}
