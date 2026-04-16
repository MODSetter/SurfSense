"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function BuyPagesPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params?.search_space_id ?? "";

	useEffect(() => {
		router.replace(`/dashboard/${searchSpaceId}/buy-more`);
	}, [router, searchSpaceId]);

	return null;
}
