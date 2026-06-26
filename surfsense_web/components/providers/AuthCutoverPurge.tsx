"use client";

import { useEffect } from "react";

const CUTOVER_FLAG_KEY = "surfsense_auth_cutover_v1_complete";
const LEGACY_BEARER_TOKEN_KEY = "surfsense_bearer_token";
const LEGACY_REFRESH_TOKEN_KEY = "surfsense_refresh_token";

export function AuthCutoverPurge() {
	useEffect(() => {
		try {
			if (localStorage.getItem(CUTOVER_FLAG_KEY) === "true") return;
			localStorage.removeItem(LEGACY_BEARER_TOKEN_KEY);
			localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
			localStorage.setItem(CUTOVER_FLAG_KEY, "true");
		} catch {
			// Storage can be unavailable in private mode; cookie auth still works.
		}
	}, []);

	return null;
}
