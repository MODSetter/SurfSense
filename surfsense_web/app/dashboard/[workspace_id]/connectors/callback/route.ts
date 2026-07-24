import { type NextRequest, NextResponse } from "next/server";
import { OAUTH_RESULT_COOKIE, type OAuthCallbackResult } from "@/contracts/types/oauth.types";

export async function GET(
	request: NextRequest,
	{ params }: { params: Promise<{ workspace_id: string }> }
) {
	const { workspace_id } = await params;
	const searchParams = request.nextUrl.searchParams;

	const payload: OAuthCallbackResult = {
		success: searchParams.get("success"),
		error: searchParams.get("error"),
		connector: searchParams.get("connector"),
		connectorId: searchParams.get("connectorId"),
	};
	const result = JSON.stringify(payload);

	const response = new NextResponse(null, {
		status: 302,
		headers: {
			// Land on the connectors panel so `useConnectorDialog` (mounted there)
			// consumes the result cookie and continues the indexing/edit flow.
			Location: `/dashboard/${workspace_id}/connectors`,
		},
	});
	response.cookies.set(OAUTH_RESULT_COOKIE, result, {
		path: "/",
		maxAge: 60,
		httpOnly: false,
		sameSite: "lax",
	});

	return response;
}
