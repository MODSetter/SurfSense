"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function BuyPagesPage() {
	const router = useRouter();
	const params = useParams();
	const workspaceId = params?.workspace_id ?? "";

	useEffect(() => {
		router.replace(`/dashboard/${workspaceId}/buy-more`);
	}, [router, workspaceId]);

	return null;
}
