"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/hooks/use-session";

/** No landing page: `/` sends a signed-in user to the dashboard and anyone else to login. */
export default function RootPage() {
	const router = useRouter();
	const session = useSession();

	useEffect(() => {
		if (session.status === "loading") return;
		router.replace(session.status === "authenticated" ? "/dashboard" : "/login");
	}, [router, session.status]);

	return null;
}
