"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function YouTubeRedirect() {
	const params = useParams();
	const router = useRouter();
	const search_space_id = params.search_space_id as string;

	useEffect(() => {
		router.replace(`/dashboard/${search_space_id}/sources/add?tab=youtube`);
	}, [search_space_id, router]);

	return null;
}
