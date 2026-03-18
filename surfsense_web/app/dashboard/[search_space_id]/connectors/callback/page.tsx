"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Spinner } from "@/components/ui/spinner";

const OAUTH_RESULT_KEY = "connector_oauth_result";

export default function ConnectorCallbackPage({
	params,
}: {
	params: { search_space_id: string };
}) {
	const router = useRouter();
	const searchParams = useSearchParams();

	useEffect(() => {
		const result = {
			success: searchParams.get("success"),
			error: searchParams.get("error"),
			connector: searchParams.get("connector"),
			connectorId: searchParams.get("connectorId"),
		};

		sessionStorage.setItem(OAUTH_RESULT_KEY, JSON.stringify(result));
		router.replace(`/dashboard/${params.search_space_id}/new-chat`);
	}, [searchParams, router, params.search_space_id]);

	return (
		<div className="flex items-center justify-center h-screen">
			<Spinner size="lg" />
		</div>
	);
}
