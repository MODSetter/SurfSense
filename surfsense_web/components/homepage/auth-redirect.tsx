"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/hooks/use-session";

export function AuthRedirect() {
	const router = useRouter();
	const session = useSession();

	useEffect(() => {
		if (session.status === "authenticated") {
			router.replace("/dashboard");
		}
	}, [router, session.status]);

	return null;
}
