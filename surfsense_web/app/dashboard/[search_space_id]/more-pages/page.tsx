"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

// Legacy route kept as a redirect: older "insufficient credits" notifications
// and bookmarks may still point at /more-pages.
export default function MorePagesPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params?.search_space_id ?? "";

	useEffect(() => {
		router.replace(`/dashboard/${searchSpaceId}/earn-credits`);
	}, [router, searchSpaceId]);

	return null;
}
