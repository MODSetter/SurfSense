"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getBearerToken } from "@/lib/auth-utils";

export function AuthRedirect() {
	const router = useRouter();

	useEffect(() => {
		if (getBearerToken()) {
			router.replace("/dashboard");
		}
	}, [router]);

	return null;
}
