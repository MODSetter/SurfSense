"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SearchSpaceDashboardPage() {
	const router = useRouter();
	const { search_space_id } = useParams();

	useEffect(() => {
		router.push(`/dashboard/${search_space_id}/chats`);
	}, []);

	return <></>;
}
