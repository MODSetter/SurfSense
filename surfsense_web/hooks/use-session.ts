"use client";

import { useCallback, useEffect, useState } from "react";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

type SessionState =
	| { status: "loading"; authenticated: false; accessExpiresAt: null }
	| { status: "authenticated"; authenticated: true; accessExpiresAt: number | null }
	| { status: "unauthenticated"; authenticated: false; accessExpiresAt: null };

export function useSession() {
	const [state, setState] = useState<SessionState>({
		status: "loading",
		authenticated: false,
		accessExpiresAt: null,
	});

	const refresh = useCallback(async () => {
		try {
			const response = await authenticatedFetch(buildBackendUrl("/auth/session"), {
				skipAuthRedirect: true,
			});
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
