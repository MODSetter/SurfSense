"use client";

import { useCallback, useEffect, useState } from "react";
import { refreshSession } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";

type SessionState =
	| { status: "loading"; authenticated: false; accessExpiresAt: null }
	| { status: "authenticated"; authenticated: true; accessExpiresAt: number | null }
	| { status: "unauthenticated"; authenticated: false; accessExpiresAt: null };

async function getSessionHeaders(): Promise<HeadersInit> {
	if (typeof window === "undefined" || !window.electronAPI?.getAccessToken) {
		return {};
	}

	const token = await window.electronAPI.getAccessToken();
	return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchSession(): Promise<Response> {
	return fetch(buildBackendUrl("/auth/session"), {
		credentials: "include",
		headers: await getSessionHeaders(),
	});
}

export function useSession() {
	const [state, setState] = useState<SessionState>({
		status: "loading",
		authenticated: false,
		accessExpiresAt: null,
	});

	const refresh = useCallback(async () => {
		try {
			let response = await fetchSession();
			if (response.status === 401) {
				const refreshed = await refreshSession();
				if (refreshed) {
					response = await fetchSession();
				}
			}
			if (!response.ok) {
				setState({
					status: "unauthenticated",
					authenticated: false,
					accessExpiresAt: null,
				});
				return;
			}
			const data = (await response.json()) as {
				authenticated: boolean;
				access_expires_at: number | null;
			};
			setState({
				status: "authenticated",
				authenticated: true,
				accessExpiresAt: data.access_expires_at,
			});
		} catch {
			setState({
				status: "unauthenticated",
				authenticated: false,
				accessExpiresAt: null,
			});
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	return { ...state, refresh };
}
