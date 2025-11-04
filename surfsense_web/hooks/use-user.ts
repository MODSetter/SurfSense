"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

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
				const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/users/me`, {
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				});

				if (response.status === 401) {
					// Clear token and redirect to home
					localStorage.removeItem("surfsense_bearer_token");
					window.location.href = "/";
					throw new Error("Unauthorized: Redirecting to login page");
				}

				if (!response.ok) {
					throw new Error(`Failed to fetch user: ${response.status}`);
				}

				const data = await response.json();
				setUser(data);
				setError(null);
			} catch (err: any) {
				setError(err.message || "Failed to fetch user");
				console.error("Error fetching user:", err);
			} finally {
				setLoading(false);
			}
		};

		fetchUser();
	}, []);

	return { user, loading, error };
}
