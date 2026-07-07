"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

// Legacy route kept as a redirect: older "insufficient credits" notifications
// and bookmarks may still point at /more-pages.
export default function MorePagesPage() {
	const router = useRouter();
	const params = useParams();
	const workspaceId = params?.workspace_id ?? "";

	useEffect(() => {
		router.replace(`/dashboard/${workspaceId}/earn-credits`);
	}, [router, workspaceId]);

	return null;
}
